# The daily console. The menu is in the order the work actually happens: steps 1-5 make one video, and each
# one remembers what the previous one chose, so a normal day never needs the sections below them.
#
#   python pipeline\menu.py                        the newest scripts\topics_*.txt
#   python pipeline\menu.py scripts\topics_1103.txt
#
# Normally started by chrh.bat, which gives it its own window, a title and a UTF-8 console.
#
# It does nothing on its own: every action is one of the scripts you would have typed, run exactly as it is,
# with the output printed live. Two small things it keeps for itself, both in work\: published.json (which
# videos have gone out) and current.json (the project you are in the middle of).
import os, sys, json, glob, datetime, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
os.chdir(HERE)

try: sys.stdout.reconfigure(encoding="utf-8")      # Cyrillic and box drawing, whatever the code page says
except Exception: pass

import autoplan, build, finish

CURRENT = os.path.join(ROOT, "work", "current.json")
LIB = os.path.join(HERE, "library.json")
W = 78


# ------------------------------------------------------------------ console
class C:
    OFF = "\033[0m"; B = "\033[1m"; INV = "\033[7m"
    CY = "\033[96m"; GR = "\033[92m"; YE = "\033[93m"; RE = "\033[91m"
    WH = "\033[97m"; GY = "\033[90m"; BL = "\033[94m"


def enable_colour():
    if os.name != "nt": return sys.stdout.isatty()
    try:
        import ctypes
        k = ctypes.windll.kernel32
        h = k.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if not k.GetConsoleMode(h, ctypes.byref(mode)): return False
        return bool(k.SetConsoleMode(h, mode.value | 0x0004))
    except Exception:
        return False


COLOUR = enable_colour()
if not COLOUR:
    for n in dir(C):
        if not n.startswith("_") and isinstance(getattr(C, n), str): setattr(C, n, "")


def wide_ok():
    try:
        "█│Ж".encode(sys.stdout.encoding or "ascii"); return True
    except Exception:
        return False


WIDE = wide_ok()
G = {"tl": "┌", "tr": "┐", "bl": "└", "br": "┘", "h": "─", "v": "│",
     "dot": "·", "arrow": "▸", "dash": "—"} if WIDE else \
    {"tl": "+", "tr": "+", "bl": "+", "br": "+", "h": "-", "v": "|", "dot": ".", "arrow": ">", "dash": "-"}

BLOCK = [
    " ██████╗██╗  ██╗██████╗ ██╗  ██╗",
    "██╔════╝██║  ██║██╔══██╗██║  ██║",
    "██║     ███████║██████╔╝███████║",
    "██║     ██╔══██║██╔══██╗██╔══██║",
    "╚██████╗██║  ██║██║  ██║██║  ██║",
    " ╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝",
] if WIDE else [
    "  ####  #    # ####   #    # ", " #      #    # #   #  #    # ", " #      ###### ####   ###### ",
    " #      #    # #  #   #    # ", "  ####  #    # #   #  #    # ",
]

_term = None


def keys_on():
    global _term
    if os.name == "nt" or not sys.stdin.isatty() or _term is not None: return
    try:
        import termios, tty
        fd = sys.stdin.fileno()
        _term = termios.tcgetattr(fd)
        tty.setcbreak(fd)
        m = termios.tcgetattr(fd); m[3] &= ~termios.ECHO
        termios.tcsetattr(fd, termios.TCSADRAIN, m)
    except Exception:
        _term = None


def keys_off():
    global _term
    if _term is None: return
    try:
        import termios
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, _term)
    except Exception: pass
    _term = None


def getkey():
    """One keypress -> 'up' 'down' 'enter' 'esc' or the character. None when this console cannot do it."""
    try:
        if os.name == "nt":
            import msvcrt
            ch = msvcrt.getwch()
            if ch in ("\x00", "\xe0"):
                return {"H": "up", "P": "down", "K": "left", "M": "right"}.get(msvcrt.getwch(), "")
            if ch == "\r": return "enter"
            if ch == "\x1b": return "esc"
            if ch == "\x03": raise KeyboardInterrupt
            return ch.lower()
        if _term is None: return None
        import select
        fd = sys.stdin.fileno()
        # os.read, not sys.stdin.read: the buffered reader would swallow the rest of an escape sequence into
        # its own buffer, select would see nothing pending, and every arrow would look like Esc.
        ch = os.read(fd, 1).decode("utf-8", "ignore")
        if ch == "\x1b":
            nxt = os.read(fd, 2).decode("utf-8", "ignore") if select.select([fd], [], [], 0.05)[0] else ""
            return {"[A": "up", "[B": "down", "[D": "left", "[C": "right"}.get(nxt, "esc")
        if ch in ("\r", "\n"): return "enter"
        if ch == "\x03": raise KeyboardInterrupt
        return ch.lower()
    except KeyboardInterrupt:
        raise
    except Exception:
        return None


# ------------------------------------------------------------------ state kept between steps
def jload(p, default):
    try: return json.load(open(p, encoding="utf-8"))
    except Exception: return default


def jsave(p, v):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(v, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def script_files():
    return sorted(glob.glob(os.path.join(ROOT, "scripts", "topics_*.txt")), key=os.path.getmtime, reverse=True)


def keys_of(path):
    try: return [v["key"] for v in autoplan.parse_batch(open(path, encoding="utf-8").read())]
    except Exception: return []


def project_of(name):
    """springlock3.mp4 -> springlock. The shop names its files by job, so the prefix is the project."""
    return os.path.splitext(name)[0].rstrip("0123456789") or os.path.splitext(name)[0]


def projects():
    """Every project in the library: clips, how many are described, whether its gate is lifted."""
    clips = jload(LIB, {}).get("clips", {})
    out = {}
    for n, r in clips.items():
        g = out.setdefault(project_of(n), {"clips": 0, "on": 0, "described": 0, "loose": 0})
        g["clips"] += 1
        g["on"] += bool(r.get("enabled"))
        g["described"] += bool(r.get("enabled") and r.get("segments"))
        g["loose"] += bool(r.get("sharp") or r.get("motion"))
    return out


def work_size():
    total = 0
    for base, _, files in os.walk(os.path.join(ROOT, "work")):
        for n in files:
            try: total += os.path.getsize(os.path.join(base, n))
            except OSError: pass
    return total


def human(b):
    return f"{b / 2**30:.1f} ГБ" if b >= 2**30 else f"{b / 2**20:.0f} МБ"


# ------------------------------------------------------------------ the screen
def banner_lines():
    out = [""] + [C.CY + C.B + "   " + l + C.OFF for l in BLOCK]
    out.append(C.GY + f"    car hauler repair houston  {G['dot']}  video pipeline" + C.OFF)
    return out


def board_lines(st):
    d = finish.outdir()
    shown = [k for k in st["keys"] if not st["only"] or k in st["only"]]
    head = f"  {C.WH}{C.B}{os.path.relpath(st['path'], ROOT)}{C.OFF}   {C.GY}{len(shown)} ролик(ов){C.OFF}"
    if st["cur"].get("prefix"):
        head += f"   {C.CY}проект: {st['cur']['prefix']}{C.OFF}"
    out = ["", head, C.GY + "  " + G["h"] * W + C.OFF,
           f"  {C.GY}{'КЛЮЧ':15s}{'ОЗВУЧКА':10s}{'СОБРАНО':31s}СТАТУС{C.OFF}"]
    voiced = built = ready = 0
    for i, k in enumerate(shown):
        vo = os.path.exists(autoplan.vo_path(k))
        plain, blurred = finish.outputs(k, d)
        voiced += bool(vo); built += bool(plain); ready += bool(blurred)
        if i < 9:
            name = (C.WH + os.path.basename(plain[0])[:30] + C.OFF) if plain else (C.GY + G["dash"] + C.OFF)
            if blurred: stt = f"{C.GR}{C.B}ГОТОВ{C.OFF}"
            elif plain: stt = f"{C.YE}без блюра{C.OFF}"
            else: stt = f"{C.GY}{G['dash']}{C.OFF}"
            ok = (C.GR + "есть" + C.OFF) if vo else (C.GY + "нет" + C.OFF)
            out.append(f"  {C.WH}{k:15s}{C.OFF}{ok.ljust(10 + len(C.GR + C.OFF))}"
                       f"{name.ljust(31 + len(C.WH + C.OFF))}{stt}")
    if len(shown) > 9: out.append(f"  {C.GY}... и ещё {len(shown) - 9}{C.OFF}")
    out.append(C.GY + "  " + G["h"] * W + C.OFF)
    out.append(f"  {C.GY}озвучено {voiced} из {len(shown)}  {G['dot']}  собрано {built}{C.OFF}" +
               (f"   {C.GR}{C.B}{ready} готово{C.OFF}" if ready else ""))
    return out


# id, letter, label (text or a function of the state), two lines of help, what it runs
ITEMS = [
    ("~", "", "ПОРЯДОК НА СЕГОДНЯ", "", ""),
    ("look", "1", "Новый проект: посмотреть и описать клипы", [
        "Берёт новое из footage\\, спрашивает пару слов о работе и смотрит клипы.",
        "Описание с контекстом — отсюда потом и порядок кадров, и текст."], "описание клипов"),
    ("write", "2", "Написать скрипт по клипам", [
        "Пишет закадровый текст по тому, что снято. Длину задаёшь в секундах.",
        "Сам подставит проект из шага 1 и выберет этот файл скриптов дальше."], "script.py"),
    ("make", "3", "Озвучить и собрать ролик", [
        "Озвучка, подбор кадров под слова, рендер, блюр лиц. Минут десять.",
        "В конце пишет, какой файл публиковать."], "voice.py + plan_ai.py"),
    ("check", "4", "Посмотреть, что получилось", [
        "Контакт-лист: сетка кадров из ролика. И открывает папку с результатом.",
        "Быстрее, чем смотреть целиком: сразу видно, если кадр не совпал с текстом."], "chrh.py sheet"),
    ("~", "", "ПО ОТДЕЛЬНОСТИ", "", ""),
    ("voice", "V", "Только озвучить", [
        "Записывает mp3 по скриптам и останавливается. Ролик не собирает.",
        "Если mp3 уже есть, он остаётся — перезаписать можно шагом 3."], "voice.py"),
    ("render", "M", "Только собрать (озвучка уже есть)", [
        "Подбор кадров, рендер и блюр по готовым mp3. В ElevenLabs не ходит.",
        "Для пересборки после правки клипов или порога качества."], "plan_ai.py"),
    ("dry", "D", "Показать раскладку кадров, не собирая", [
        "Какой кусок какого клипа встанет под какие слова, и почему. Без рендера.",
        "Проверить монтаж, прежде чем тратить минуты на ffmpeg."], "plan_ai.py --dry"),
    ("blur", "B", "Заблюрить лица ещё раз", [
        "Шаг 3 блюрит сам. Это на случай, если в таблице стоит «без блюра».",
        "Ничего не выкладываем с узнаваемым лицом — правило цеха."], "finish.py"),
    ("~", "", "МАТЕРИАЛЫ", "", ""),
    ("library", "5", "Что есть в библиотеке", [
        "Проекты: сколько клипов и сколько из них видит планировщик.",
        "Ноль в «описано» — проект для сборки пока не существует."], ""),
    ("diag", "6", "Проверить качество клипов проекта", [
        "Резкость, тряска и разрешение по каждому клипу.",
        "Нули в PASS@700 почти везде — материал мягкий, сборка выйдет мутной."], "diag.py"),
    ("describe", "7", "Описать клипы, которые ещё не описаны", [
        "Догоняет всё, что лежит в библиотеке с прошлых раз без описания.",
        "Нужно для общих роликов про сервис, где кадры берутся со всей библиотеки."], "describe.py"),
    ("~", "", "НАСТРОЙКИ", "", ""),
    ("pick", "F", lambda st: f"Файл скриптов: {os.path.basename(st['path'])}", [
        "Какой файл со скриптами сейчас в работе. Шаг 2 ставит его сам.",
        "Менять руками нужно, только если вернулся к старой партии."], ""),
    ("only", "K", lambda st: "Собирать: " + (", ".join(st["only"]) if st["only"] else "все ролики файла"), [
        "Ограничивает шаги 3 и 4 одним ключом: пересборка не тронет остальные.",
        "Пустой ответ возвращает весь файл."], ""),
    ("gate", "T", lambda st: "Порог качества: " + (
        f"снят у {', '.join(st['loose'])}" if st["loose"] else "включён везде"), [
        "Обычно включён: мягкие и трясущиеся секунды в кадр не попадают.",
        "Снимать только для материала, который нельзя переснять."], "tune.py"),
    ("openout", "O", "Открыть папку с результатом", ["Открывает output\\ в проводнике.", ""], ""),
    ("clean", "C", lambda st: f"Очистить work\\ ({human(st['work'])})", [
        "Удаляет промежуточное видео — именно оно съедает диск. Спросит сначала.",
        "Кэши не трогает: без них придётся заново мерить все клипы."], ""),
    ("quit", "Q", "Выход", ["Закрывает окно.", ""], ""),
]
RUNNABLE = [i for i in ITEMS if i[0] != "~"]
BY_LETTER = {i[1].lower(): n for n, i in enumerate(RUNNABLE)}


def label_of(it, st):
    return it[2](st) if callable(it[2]) else it[2]


def menu_lines(sel, st):
    out = [""]
    for it in ITEMS:
        if it[0] == "~":
            out.append(f"  {C.GY}{it[2]}{C.OFF}"); continue
        on = RUNNABLE[sel][0] == it[0]
        text = label_of(it, st)
        row = f" {G['arrow'] if on else ' '} [{it[1]}] {text} "
        out.append("  " + ((C.INV + C.B + row.ljust(58) + C.OFF) if on
                           else f" {C.YE}{C.B}[{it[1]}]{C.OFF} {C.WH}{text}{C.OFF}"))
    return out


def help_lines(sel):
    """The panel under the menu. The box is W wide including its borders, so the text gets W-4."""
    _, _, _, help_, runs = RUNNABLE[sel]
    inner, text = W - 2, W - 4
    title = " что это делает "
    out = ["", f"  {C.GY}{G['tl']}{G['h']}{title}{G['h'] * (inner - 1 - len(title))}{G['tr']}{C.OFF}"]
    for line, col in [(l, C.WH) for l in (help_ or ["", ""])[:2]] + [(runs and f"запускает: {runs}", C.GY)]:
        out.append(f"  {C.GY}{G['v']}{C.OFF} {col}{(line or '')[:text].ljust(text)}{C.OFF} {C.GY}{G['v']}{C.OFF}")
    out.append(f"  {C.GY}{G['bl']}{G['h'] * inner}{G['br']}{C.OFF}")
    return out


def draw(st, sel):
    body = banner_lines()
    body += [f"  {C.RE}! {w}{C.OFF}" for w in st["warn"]]
    body += board_lines(st)
    body += menu_lines(sel, st)
    body += help_lines(sel)
    body += ["", f"  {C.GY}стрелки {G['dash']} выбор  {G['dot']}  Enter {G['dash']} запустить  {G['dot']}  "
                 f"буква {G['dash']} сразу  {G['dot']}  Q {G['dash']} выход{C.OFF}"]
    sys.stdout.write("\033[H" + "".join(l + "\033[K\n" for l in body) + "\033[J")
    sys.stdout.flush()


# ------------------------------------------------------------------ running things
def run(script, *a, pause=True, quiet=False):
    """Run one of the pipeline scripts. quiet keeps its output off the screen and returns it instead."""
    cmd = [sys.executable, os.path.join(HERE, script)] + [str(x) for x in a if x not in (None, "")]
    if quiet:
        p = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True,
                           encoding="utf-8", errors="replace")
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    print(f"\n{C.GY}> {' '.join(os.path.relpath(c, ROOT) if os.path.isabs(c) else c for c in cmd[1:])}{C.OFF}")
    print(C.GY + "  " + G["h"] * W + C.OFF)
    try:
        code = subprocess.call(cmd, cwd=ROOT)
    except KeyboardInterrupt:
        print(f"\n{C.YE}прервано{C.OFF}"); code = 1
    print(C.GY + "  " + G["h"] * W + C.OFF)
    print(f"  {C.GR}готово{C.OFF}" if code == 0 else f"  {C.RE}ошибка (код {code}){C.OFF}")
    if pause: hold()
    return code


def hold():
    try: input(f"{C.GY}  Enter {G['dash']} назад в меню {C.OFF}")
    except (EOFError, KeyboardInterrupt): print()


def ask(q, default=""):
    try: v = input(q).strip()
    except (EOFError, KeyboardInterrupt): print(); return ""
    return v or default


def choose(title, rows, allow_blank=True):
    """rows = [(value, label)]. Returns the chosen value, or '' ."""
    if not rows: return ""
    print(f"\n  {C.WH}{C.B}{title}{C.OFF}\n")
    for i, (_, lab) in enumerate(rows, 1):
        print(f"   {C.YE}{i:2d}{C.OFF}  {lab}")
    v = ask(f"\n  {C.WH}номер{' (пусто — отмена)' if allow_blank else ''} : {C.OFF}")
    return rows[int(v) - 1][0] if v.isdigit() and 1 <= int(v) <= len(rows) else ""


# ------------------------------------------------------------------ the five steps
def step_look(st):
    """Scan whatever is new, let him pick the project from a list, then describe it with the job in mind."""
    print(f"\n  {C.GY}смотрю, что нового в footage\\{C.OFF}")
    code, out = run("chrh.py", "scan", quiet=True)
    if code != 0:
        print(out.strip()[-1500:]); print(f"  {C.RE}сканирование не прошло{C.OFF}"); hold(); return
    # David's three-word auto-tags go past here and are not worth showing: the real description comes next.
    added = [l for l in out.splitlines() if "tagged" in l.lower()]
    print(f"  {C.GR}{added[-1] if added else 'новых файлов нет'}{C.OFF}")

    P = projects()
    if not P:
        print(f"\n  {C.YE}в footage\\ пусто{C.OFF}"); hold(); return
    rows = []
    for name, g in sorted(P.items(), key=lambda kv: -kv[1]["clips"]):
        tail = (f"{C.GR}описан{C.OFF}" if g["described"] >= g["on"] and g["on"]
                else f"{C.YE}описано {g['described']} из {g['on']}{C.OFF}")
        rows.append((name, f"{C.WH}{name:24s}{C.OFF}{g['clips']:3d} клип(ов)   {tail}"))
    prefix = choose("какой проект снимали?", rows)
    if not prefix: return

    known = jload(CURRENT, {}).get("notes", {}).get(prefix, "")
    print(f"\n  {C.GY}пара слов о работе: что за трейлер, что делали и в каком порядке.{C.OFF}")
    print(f"  {C.GY}это уходит в глаза модели — она назовёт детали правильно.{C.OFF}")
    if known: print(f"  {C.GY}прошлый раз: {known}{C.OFF}")
    note = ask(f"  {C.WH}: {C.OFF}", known)
    if not note:
        print(f"  {C.YE}без описания работы смысла мало — отменяю{C.OFF}"); hold(); return

    code = run("describe.py", prefix, "--note", note, pause=False)
    if code != 0: hold(); return
    cur = jload(CURRENT, {})
    cur["prefix"] = prefix
    cur.setdefault("notes", {})[prefix] = note
    jsave(CURRENT, cur)
    print(f"\n  {C.GR}проект {prefix} описан. Дальше шаг 2 — написать скрипт.{C.OFF}")
    hold()


def step_write(st):
    """The script, sized in seconds, written from the descriptions. Sets the file and the key for step 3."""
    cur = jload(CURRENT, {})
    prefix = cur.get("prefix", "")
    if not prefix:
        rows = [(n, f"{C.WH}{n}{C.OFF}   {g['described']} описанных клип(ов)")
                for n, g in sorted(projects().items()) if g["described"]]
        prefix = choose("по какому проекту писать?", rows)
        if not prefix: return
    note = cur.get("notes", {}).get(prefix, "")
    print(f"\n  {C.WH}проект: {prefix}{C.OFF}")
    if note: print(f"  {C.GY}о работе: {note}{C.OFF}")
    secs = ask(f"  {C.WH}сколько секунд должен идти ролик [45] : {C.OFF}", "45")
    out = os.path.join(ROOT, "scripts", f"topics_{datetime.date.today():%m%d}.txt")
    before = set(keys_of(out)) if os.path.exists(out) else set()
    if run("script.py", "--only", prefix, "--seconds", secs, "--note", note, "--out", out, pause=False) != 0:
        hold(); return
    new = [k for k in keys_of(out) if k not in before]
    st["path"], st["keys"] = out, keys_of(out)
    st["only"] = new                                  # step 3 builds exactly what was just written
    cur["prefix"], cur["seconds"] = prefix, secs
    jsave(CURRENT, cur)
    print(f"\n  {C.GR}скрипт в scripts\\{os.path.basename(out)}" +
          (f", ключ: {', '.join(new)}" if new else "") + f"{C.OFF}")
    print(f"  {C.GY}прочитай его, поправь прямо в файле если надо, потом шаг 3.{C.OFF}")
    hold()


def step_voice(st, pause=True):
    """The mp3 for every script that has none yet."""
    return run("voice.py", st["path"], *st["only"], pause=pause)


def step_render(st, pause=True):
    """Plan, render and blur from the mp3 that is already there. Never calls ElevenLabs."""
    prefix = jload(CURRENT, {}).get("prefix", "")
    return run("plan_ai.py", st["path"], *st["only"], *(["--only", prefix] if prefix else []), pause=pause)


def step_make(st):
    """Both, in order. A missing or half-written mp3 would put every cut in the wrong place, so a failed
    voice-over stops here instead of building something that cannot be right."""
    if step_voice(st, pause=False) != 0:
        print(f"  {C.RE}озвучка не получилась — ничего не собирал{C.OFF}"); hold(); return
    step_render(st)


def step_check(st):
    d = finish.outdir()
    built = [k for k in (st["only"] or st["keys"]) if finish.outputs(k, d)[0]]
    if not built:
        print(f"\n  {C.YE}собранных роликов пока нет{C.OFF}"); hold(); return
    run("chrh.py", "sheet", *built, pause=False)
    try:
        if os.name == "nt": os.startfile(d)
        else: subprocess.call(["xdg-open", d])
    except Exception: pass
    print(f"\n  {C.GY}папка с результатом открыта{C.OFF}")
    hold()


# ------------------------------------------------------------------ the rest
def show_library(st):
    P = projects()
    if not P:
        print(f"\n  {C.YE}библиотека пустая{C.OFF}"); hold(); return
    total = sum(g["clips"] for g in P.values())
    print(f"\n  {C.WH}{C.B}{total} клип(ов), {len(P)} проект(ов){C.OFF}")
    print(C.GY + "  " + G["h"] * W + C.OFF)
    print(f"  {C.GY}{'ПРОЕКТ':26s}{'КЛИПОВ':9s}{'В РАБОТЕ':11s}{'ОПИСАНО':10s}ПОРОГ{C.OFF}")
    for n, g in sorted(P.items(), key=lambda kv: -kv[1]["clips"]):
        col = C.GR if g["described"] >= g["on"] and g["on"] else (C.YE if g["described"] else C.GY)
        print(f"  {C.WH}{n[:25]:26s}{C.OFF}{g['clips']:<9d}{g['on']:<11d}{col}{g['described']:<10d}{C.OFF}"
              f"{(C.YE + 'снят' + C.OFF) if g['loose'] else C.GY + 'обычный' + C.OFF}")
    print(C.GY + "  " + G["h"] * W + C.OFF)
    nd = sum(g["on"] - g["described"] for g in P.values())
    if nd: print(f"  {C.YE}{nd} клип(ов) без описания — планировщик их не видит (шаг 8){C.OFF}")
    hold()


def set_gate(st):
    P = projects()
    rows = [(n, f"{C.WH}{n:24s}{C.OFF}" +
             (f"{C.YE}порог снят{C.OFF}" if g["loose"] else f"{C.GY}обычный порог{C.OFF}"))
            for n, g in sorted(P.items())]
    p = choose("у какого проекта менять порог качества?", rows)
    if not p: return
    on = not P[p]["loose"]
    m = ask(f"\n  {C.WH}[с]нять порог или [в]ернуть обычный "
            f"[{'с' if on else 'в'}] : {C.OFF}", "с" if on else "в").lower()
    if m.startswith(("с", "f")): run("tune.py", "free", p)
    elif m.startswith(("в", "g")): run("tune.py", "gate", p)


def pick_file(st):
    files = script_files()
    rows = [(f, f"{C.WH}{os.path.basename(f):28s}{C.OFF}{C.GY}{len(keys_of(f))} ролик(ов){C.OFF}")
            for f in files[:15]]
    f = choose("какой файл со скриптами взять?", rows)
    if f: st["path"], st["keys"], st["only"] = f, keys_of(f), []


def set_only(st):
    print(f"\n  {C.GY}ролики в файле: {', '.join(st['keys']) or 'нет'}{C.OFF}")
    v = ask(f"  {C.WH}ключ(и) через пробел, пусто — все : {C.OFF}").lower().split()
    bad = [x for x in v if x not in st["keys"]]
    if bad:
        print(f"  {C.RE}в этом файле нет: {', '.join(bad)}{C.OFF}"); hold()
    st["only"] = [x for x in v if x in st["keys"]]


def cleanup(st):
    junk, size = [], 0
    for base, _, files in os.walk(os.path.join(ROOT, "work")):
        for n in files:
            if n.lower().endswith((".mp4", ".mov", ".mkv", ".ts", ".nut", ".wav", ".trf", ".y4m")):
                p = os.path.join(base, n)
                try: size += os.path.getsize(p)
                except OSError: continue
                junk.append(p)
    if not junk:
        print(f"\n  {C.GR}в work\\ нет промежуточного видео{C.OFF}"); hold(); return
    print(f"\n  {C.WH}{len(junk)} файл(ов), {C.B}{human(size)}{C.OFF}")
    for p in junk[:8]: print(f"   {C.GY}{os.path.relpath(p, ROOT)}{C.OFF}")
    if len(junk) > 8: print(f"   {C.GY}... и ещё {len(junk) - 8}{C.OFF}")
    print(f"  {C.GY}кэши не трогаю: без них придётся заново мерить все клипы{C.OFF}")
    if ask(f"\n  {C.YE}удалить? напиши да : {C.OFF}").lower() not in ("да", "yes", "y"):
        print(f"  {C.GY}оставил как есть{C.OFF}"); hold(); return
    gone = 0
    for p in junk:
        try: os.remove(p); gone += 1
        except OSError as e: print(f"  {C.RE}не смог удалить {os.path.basename(p)}: {e}{C.OFF}")
    print(f"  {C.GR}удалено {gone} файл(ов){C.OFF}")
    st["work"] = work_size()
    hold()


def act(ident, st):
    if ident == "quit": return False
    elif ident == "look": step_look(st)
    elif ident == "write": step_write(st)
    elif ident == "make": step_make(st)
    elif ident == "voice": step_voice(st)
    elif ident == "render": step_render(st)
    elif ident == "check": step_check(st)
    elif ident == "library": show_library(st)
    elif ident == "describe": run("describe.py")
    elif ident == "diag":
        rows = [(n, f"{C.WH}{n}{C.OFF}   {g['clips']} клип(ов)") for n, g in sorted(projects().items())]
        p = choose("какой проект проверить?", rows)
        if p: run("diag.py", p)
    elif ident == "gate": set_gate(st)
    elif ident == "dry": run("plan_ai.py", st["path"], *st["only"], "--dry")
    elif ident == "blur": run("finish.py", st["path"], *st["only"])
    elif ident == "openout":
        d = finish.outdir()
        try:
            if os.name == "nt": os.startfile(d)
            else: subprocess.call(["xdg-open", d])
            print(f"\n  {C.GR}открыл {os.path.relpath(d, ROOT)}\\{C.OFF}")
        except Exception as e:
            print(f"\n  {C.RE}не открылось: {e}{C.OFF}\n  {d}")
        hold()
    elif ident == "pick": pick_file(st)
    elif ident == "only": set_only(st)
    elif ident == "clean": cleanup(st)
    return True


# ------------------------------------------------------------------ run
path = None
if len(sys.argv) > 1:
    p = sys.argv[1]
    p = p if os.path.isabs(p) else os.path.join(ROOT, p)
    if os.path.isfile(p): path = p
if path is None:
    f = script_files()
    path = f[0] if f else os.path.join(ROOT, "scripts", f"topics_{datetime.date.today():%m%d}.txt")

warn = []
if not os.environ.get("ANTHROPIC_API_KEY", "").strip():
    warn.append("ANTHROPIC_API_KEY не задан — описание и подбор кадров работать не будут")
if not os.environ.get("ELEVENLABS_API_KEY", "").strip():
    warn.append("ELEVENLABS_API_KEY не задан — озвучки не будет")

st = {"path": path, "keys": keys_of(path), "only": [], "warn": warn,
      "work": work_size(), "cur": jload(CURRENT, {}), "loose": []}
sel, live = 0, True
if COLOUR: sys.stdout.write("\033[2J")

try:
    while live:
        st["cur"] = jload(CURRENT, {})
        st["loose"] = [n for n, g in projects().items() if g["loose"]]
        draw(st, sel)
        keys_on()
        k = getkey()
        keys_off()                      # anything below here may print or ask a question
        if k is None:                   # a console that cannot read single keys: type the letter instead
            try: said = input(f"\n  {C.WH}{C.B}Выбор : {C.OFF}").strip().lower()
            except (EOFError, KeyboardInterrupt): break
            k = said[:1] if said else "enter"
            if said in ("q", "quit", "exit", "й"): k = "q"

        if k == "up": sel = (sel - 1) % len(RUNNABLE)
        elif k == "down": sel = (sel + 1) % len(RUNNABLE)
        elif k == "esc": break
        elif k == "enter" or k in BY_LETTER:
            if k in BY_LETTER: sel = BY_LETTER[k]
            if COLOUR: sys.stdout.write("\033[2J\033[H")
            live = act(RUNNABLE[sel][0], st)
            st["keys"] = keys_of(st["path"])
            if COLOUR: sys.stdout.write("\033[2J")
except KeyboardInterrupt:
    pass
finally:
    keys_off()

print(f"  {C.GY}пока{C.OFF}\n")
