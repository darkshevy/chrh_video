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
import os, re, sys, json, glob, time, shutil, datetime, subprocess, textwrap

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
     "dot": "·", "arrow": "▸", "dash": "—", "done": "✓", "now": "◉", "todo": "○", "full": "●", "larr": "←"} if WIDE else \
    {"tl": "+", "tr": "+", "bl": "+", "br": "+", "h": "-", "v": "|", "dot": ".", "arrow": ">", "dash": "-",
     "done": "v", "now": "*", "todo": "o", "full": "#", "larr": "<-"}

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
    """Every project in the library: clips, and how many of the enabled ones are described."""
    clips = jload(LIB, {}).get("clips", {})
    out = {}
    for n, r in clips.items():
        g = out.setdefault(project_of(n), {"clips": 0, "on": 0, "described": 0, "desc_at": 0})
        g["clips"] += 1
        g["on"] += bool(r.get("enabled"))
        g["described"] += bool(r.get("enabled") and r.get("segments"))
        g["desc_at"] = max(g["desc_at"], r.get("desc_at", 0) if r.get("enabled") else 0)
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
# Two screens. A (the whole menu, two panels) is home. Starting a new project with [1] switches to B, a
# step-by-step screen that only offers what makes sense for the step the project is at; when step 4 is done
# the project is finished and the console goes back to A. Tab moves between the two at any time.
_ANSI = re.compile(r"\033\[[0-9;]*m")


def vlen(s):
    """Visible width: the colour codes take no room on screen but count in len()."""
    return len(_ANSI.sub("", s))


def pad(s, n):
    return s + " " * max(0, n - vlen(s))


def clip(s, n):
    """Cut s to n visible characters, keeping the colour codes intact. A line wider than its panel wraps in
    the console and drags the rest of the screen down with it."""
    if vlen(s) <= n: return s
    out, seen, i = [], 0, 0
    while i < len(s) and seen < n - 1:
        m = _ANSI.match(s, i)
        if m: out.append(m.group(0)); i = m.end(); continue
        out.append(s[i]); seen += 1; i += 1
    return "".join(out) + "…" + C.OFF


def term_cols():
    try: return shutil.get_terminal_size((120, 40)).columns
    except Exception: return 120


def progress(st):
    """[(label, done)] for the four steps of the current project, plus a hint for the step that is next.

    Everything is read from disk on each redraw, so the state stays right after a crash, a restart or a file
    edited by hand. Step 4 leaves nothing reliable in the output folder (the contact sheet's name is chrh.py's
    business), so step_check stamps the time it ran per key; a build newer than that stamp reopens the step."""
    cur = st["cur"]
    prefix = cur.get("prefix", "")
    g = projects().get(prefix) if prefix else None
    s1 = bool(g and g["on"] and g["described"] >= g["on"])
    script = cur.get("script", "")
    keys = [k for k in cur.get("keys", []) if script and k in keys_of(script)]
    # a script written before the clips were last described tells the old, wrong story: write it again
    stale = bool(keys and g and cur.get("script_at", 0) < g.get("desc_at", 0))
    s2 = bool(keys) and not stale
    d = finish.outdir()
    outs = {k: sum(finish.outputs(k, d), []) for k in keys}
    s3 = s2 and all(outs[k] for k in keys)
    checked = cur.get("checked", {})
    s4 = s3 and all(checked.get(k, 0) >= max(os.path.getmtime(p) for p in outs[k]) for k in keys)
    steps = [("ОПИСАТЬ", s1), ("СКРИПТ", s2), ("СОБРАТЬ", s3), ("ПРОВЕРИТЬ", s4)]

    if not prefix: hint = "проект не выбран"
    elif not s1: hint = f"описано {g['described'] if g else 0} из {g['on'] if g else 0} клипов"
    elif not s2: hint = ("клипы описаны заново — скрипт написан по старым описаниям, перепиши его" if stale
                         else "клипы описаны, скрипта ещё нет")
    elif not s3:
        vo = [k for k in keys if os.path.exists(autoplan.vo_path(k))]
        hint = f"{', '.join(keys)}: " + ("озвучка есть, ролик не собран" if vo else "нет озвучки и ролика")
    elif not s4: hint = f"{', '.join(keys)}: собран, контакт-лист ещё не смотрели"
    else: hint = f"{', '.join(keys)}: готов к публикации"
    return steps, hint


def first_open(steps):
    return next((i for i, (_, ok) in enumerate(steps) if not ok), None)


# ---- A: the whole menu
# id, letter, short label (text or a function of the state), help text, what it runs
ITEMS = [
    ("~", "", "ПОРЯДОК НА СЕГОДНЯ", "", ""),
    ("look", "1", "Описать клипы", "Новый проект. Берёт новое из footage\\, спрашивает пару слов о работе и "
     "смотрит каждый клип. Дальше откроется пошаговый экран проекта.", "описание клипов"),
    ("write", "2", "Написать скрипт", "Пишет закадровый текст по тому, что снято. Длину задаёшь в секундах. "
     "Сам подставит проект из шага 1 и выберет этот файл скриптов дальше.", "script.py"),
    ("make", "3", "Озвучить и собрать", "Озвучка, подбор кадров под слова, рендер. Минут десять. "
     "В конце пишет, какой файл публиковать.", "voice.py + plan_ai.py"),
    ("check", "4", "Посмотреть результат", "Контакт-лист: сетка кадров из ролика, и папка с результатом. "
     "Быстрее, чем смотреть целиком: сразу видно, если кадр не совпал с текстом.", "chrh.py sheet"),
    ("~", "", "ПО ОТДЕЛЬНОСТИ", "", ""),
    ("voice", "V", "Только озвучить", "Записывает mp3 по скриптам и останавливается. Ролик не собирает. "
     "Если mp3 уже есть, он остаётся.", "voice.py"),
    ("render", "M", "Только собрать", "Подбор кадров и рендер по готовым mp3. В ElevenLabs не ходит. "
     "Для пересборки после правки клипов или текста.", "plan_ai.py"),
    ("dry", "D", "Раскладка без сборки", "Какой кусок какого клипа встанет под какие слова, и почему. "
     "Без рендера — проверить монтаж, прежде чем тратить минуты на ffmpeg.", "plan_ai.py --dry"),
    ("blur", "B", "Заблюрить лица", "Сборка лица не блюрит: детектор ловил ржавчину и болты. Если в кадр "
     "попал человек — прогони этим пунктом. Узнаваемых лиц не выкладываем.", "finish.py"),
    ("~", "", "МАТЕРИАЛЫ", "", ""),
    ("library", "5", "Библиотека", "Проекты: сколько клипов и сколько из них видит планировщик. "
     "Ноль в «описано» — проект для сборки пока не существует.", ""),
    ("diag", "6", "Качество клипов", "Резкость, тряска и разрешение по каждому клипу. PASS@700 — справочно: "
     "отбора по нему нет, сборка просто берёт что чётче.", "diag.py"),
    ("describe", "7", "Описать остальные", "Догоняет всё, что лежит в библиотеке с прошлых раз без описания. "
     "Нужно для общих роликов про сервис, где кадры берутся со всей библиотеки.", "describe.py"),
    ("~", "", "НАСТРОЙКИ", "", ""),
    ("pick", "F", lambda st: f"Файл: {os.path.basename(st['path'])}", "Какой файл со скриптами сейчас "
     "в работе. Шаг 2 ставит его сам. Менять руками нужно, только если вернулся к старой партии.", ""),
    ("only", "K", lambda st: "Ролики: " + (", ".join(st["only"]) if st["only"] else "все"), "Ограничивает "
     "шаги 3 и 4 одним ключом: пересборка не тронет остальные. Пустой ответ возвращает весь файл.", ""),
    ("openout", "O", "Открыть output\\", "Открывает папку с готовыми роликами в проводнике.", ""),
    ("clean", "C", lambda st: f"Очистить work\\ ({human(st['work'])})", "Удаляет промежуточное видео — "
     "именно оно съедает диск. Спросит сначала. Кэши не трогает.", ""),
    ("quit", "Q", "Выход", "Закрывает окно.", ""),
]
RUNNABLE = [i for i in ITEMS if i[0] != "~"]
BY_LETTER = {i[1].lower(): n for n, i in enumerate(RUNNABLE)}
LW = 30          # left panel


def label_of(it, st):
    return it[2](st) if callable(it[2]) else it[2]


def left_lines(sel, st):
    out = ["", f"  {C.CY}{C.B}CHRH{C.OFF}"]
    for it in ITEMS:
        if it[0] == "~":
            out += ["", f"  {C.GY}{it[2]}{C.OFF}"]; continue
        text = label_of(it, st)[:LW - 7]
        if RUNNABLE[sel][0] == it[0]:
            out.append(C.INV + C.B + pad(f" {G['arrow']} {it[1]} {text}", LW - 1) + C.OFF)
        else:
            out.append(f"   {C.YE}{it[1]}{C.OFF} {C.WH}{text}{C.OFF}")
    return out


def board_lines(st, rw):
    d = finish.outdir()
    cur = st["cur"]
    shown = [k for k in st["keys"] if not st["only"] or k in st["only"]]
    head = f"{C.WH}{C.B}{os.path.basename(st['path'])}{C.OFF}  {C.GY}{G['dot']}  {len(shown)} ролик(ов){C.OFF}"
    prefix = cur.get("prefix", "")
    if prefix:
        g = projects().get(prefix, {"clips": 0, "described": 0})
        head = (f"{C.CY}{C.B}{prefix}{C.OFF}  {C.GY}{G['dot']}  {g['clips']} клип(ов)  {G['dot']}  "
                f"описано {g['described']}  {G['dot']}  {C.OFF}") + head
    kw, vw = 14, 9
    nw = max(12, rw - kw - vw - 8)
    out = ["", head, "", f"{C.GY}{'КЛЮЧ':{kw}s}{'ОЗВУЧКА':{vw}s}{'СОБРАНО':{nw}s}СТАТУС{C.OFF}"]
    voiced = built = 0
    for i, k in enumerate(shown):
        vo = os.path.exists(autoplan.vo_path(k))
        plain, blurred = finish.outputs(k, d)
        # blur is off by default, so the plain render is the finished video; a blurred copy, if any, is newer
        newest = sorted(plain + blurred, key=os.path.getmtime, reverse=True)
        voiced += bool(vo); built += bool(newest)
        if i < 9:
            name = (C.WH + os.path.splitext(os.path.basename(newest[0]))[0][:nw - 2] + C.OFF) if newest \
                else (C.GY + G["dash"] + C.OFF)
            stt = f"{C.GR}{C.B}ГОТОВ{C.OFF}" if newest else f"{C.GY}{G['dash']}{C.OFF}"
            ok = (C.GR + "есть" + C.OFF) if vo else (C.GY + "нет" + C.OFF)
            out.append(f"{C.WH}{k[:kw - 1]:{kw}s}{C.OFF}{pad(ok, vw)}{pad(name, nw)}{stt}")
    if len(shown) > 9: out.append(f"{C.GY}... и ещё {len(shown) - 9}{C.OFF}")
    if not shown: out.append(f"{C.GY}в файле пока нет скриптов{C.OFF}")
    out.append(f"{C.GY}озвучено {voiced} из {len(shown)}  {G['dot']}  собрано {built}{C.OFF}")
    return out


def box(title, rows, w):
    """A framed panel w wide. rows = [(text, colour)]; long text is wrapped, not cut."""
    inner = w - 2
    out = [f"{C.GY}{G['tl']}{G['h']}{title}{G['h'] * max(0, inner - 1 - len(title))}{G['tr']}{C.OFF}"]
    for text, col in rows:
        for line in (textwrap.wrap(text, w - 4) or [""]):
            out.append(f"{C.GY}{G['v']}{C.OFF} {col}{pad(line, w - 4)}{C.OFF} {C.GY}{G['v']}{C.OFF}")
    out.append(f"{C.GY}{G['bl']}{G['h'] * inner}{G['br']}{C.OFF}")
    return out


def draw_a(st, sel):
    rw = min(80, max(54, term_cols() - LW - 4))
    _, _, _, help_, runs = RUNNABLE[sel]
    right = [f"{C.RE}! {w}{C.OFF}" for w in st["warn"]]
    right += board_lines(st, rw)
    right += [""] + box(" что это делает ", [(help_, C.WH)] + ([(f"запускает: {runs}", C.GY)] if runs else []), rw)
    if st["cur"].get("wizard"):
        steps, hint = progress(st)
        i = first_open(steps)
        if i is not None:
            right += ["", f"{C.YE}проект {st['cur'].get('prefix', '')} в работе: шаг {i + 1} {steps[i][0]}{C.OFF}",
                      f"{C.GY}{hint}{C.OFF}",
                      f"{C.YE}{C.B}Tab{C.OFF}{C.YE} {G['dash']} вернуться к нему{C.OFF}"]
    left = left_lines(sel, st)
    foot = (f"{C.GY}стрелки {G['dash']} выбор  {G['dot']}  Enter {G['dash']} запустить  {G['dot']}  "
            f"буква {G['dash']} сразу  {G['dot']}  Q {G['dash']} выход{C.OFF}")
    n = max(len(left), len(right) + 2)
    right += [""] * (n - 2 - len(right)) + [C.GY + G["h"] * rw + C.OFF, foot]
    left += [""] * (n - len(left))
    body = [pad(clip(l, LW), LW) + f"{C.GY}{G['v']}{C.OFF} " + clip(r, rw) for l, r in zip(left, right)]
    flush(body)


# ---- B: one project, step by step
WIZ_TEXT = [
    "Claude посмотрит каждый клип проекта и запишет, что на экране по отрезкам — с учётом того, что ты "
    "написал о работе. Описанные клипы второй раз не смотрит.",
    "Claude прочитает, что видно на клипах, и напишет закадровый текст под них. Если материала мало — текст "
    "выйдет короче заказанного, и он об этом скажет. Потом прочитай скрипт и поправь, если надо.",
    "Озвучка через ElevenLabs, затем Claude раскладывает отрезки клипов под слова и ffmpeg собирает ролик. "
    "Минут десять. Если mp3 уже есть, озвучка не перезаписывается.",
    "Контакт-лист — сетка кадров из ролика — и папка с результатом. Сразу видно, если кадр не совпал с "
    "текстом. После этого проект считается готовым, и откроется общее меню.",
]


def wiz_actions(st, step):
    """[(key, label, action id)] for the step on screen. 'enter' is the main action of the step."""
    cur = st["cur"]
    if step == 0:
        a = [("enter", f"Описать клипы {cur.get('prefix', '')}", "w_describe"),
             ("n", "Уточнить описание работы", "w_note"),
             ("p", "Выбрать другой проект", "look")]
    elif step == 1:
        a = [("enter", f"Написать скрипт на {cur.get('seconds', '45')} секунд", "w_write"),
             ("s", "Другая длина ролика", "w_seconds"),
             ("n", "Уточнить описание работы", "w_note")]
    elif step == 2:
        a = [("enter", "Озвучить и собрать", "make"),
             ("e", "Открыть скрипт для правки", "w_edit"),
             ("d", "Раскладка без сборки", "dry")]
        if any(os.path.exists(autoplan.vo_path(k)) for k in st["only"]):
            a.append(("m", "Только собрать (озвучка уже есть)", "render"))
    else:
        a = [("enter", "Посмотреть результат", "check"),
             ("m", "Пересобрать", "render"),
             ("b", "Заблюрить лица", "blur")]
    if step > 0: a.append(("left", f"Назад к шагу {step}", "w_back"))
    return a


def wiz_step(st):
    steps, _ = progress(st)
    open_ = first_open(steps)
    if open_ is None: open_ = 3
    v = st.get("view")
    return (v if v is not None and v <= open_ else open_), steps, open_


def bar_lines(steps, shown, open_, w):
    """The four steps as circles joined by lines, names under them and a word under the one on screen."""
    cw = w // 4
    top, names, under = [], [], []
    for i, (name, ok) in enumerate(steps):
        if ok: col, mark, word = C.GR, G["full"], "готово"
        elif i == open_: col, mark, word = C.YE, G["now"], "вы здесь"
        else: col, mark, word = C.GY, G["todo"], ""
        if i == shown and i != open_: word = "открыт"
        left = (cw - 1) // 2
        joint = C.GR if i and steps[i - 1][1] else C.GY
        seg = (" " * left if i == 0 else joint + G["h"] * (left - 1) + C.OFF + " ")
        nxt = C.GR if ok else C.GY
        seg += col + C.B + mark + C.OFF + (" " + nxt + G["h"] * (cw - left - 2) + C.OFF if i < 3 else "")
        top.append(seg)
        label = f"{i + 1} {name}"
        names.append(col + C.B + label.center(cw) + C.OFF)
        under.append((C.YE if i == open_ else C.GY) + word.center(cw) + C.OFF)
    return ["  " + "".join(top), "  " + "".join(names), "  " + "".join(under)]


def draw_b(st, sel):
    w = min(84, max(60, term_cols() - 4))
    step, steps, open_ = wiz_step(st)
    cur = st["cur"]
    prefix = cur.get("prefix", "")
    g = projects().get(prefix, {"clips": 0, "on": 0, "described": 0})
    _, hint = progress(st)
    note = cur.get("notes", {}).get(prefix, "")
    body = [""] + [f"  {C.RE}! {x}{C.OFF}" for x in st["warn"]] + [""]
    body += bar_lines(steps, step, open_, w)
    body += ["", f"  {C.GY}{G['v']} ПРОЕКТ{C.OFF}", f"  {C.GY}{G['v']}{C.OFF} {C.CY}{C.B}{prefix}{C.OFF}"]
    about = f"{g['clips']} клип(ов), описано {g['described']} из {g['on']}"
    if st["only"] and step >= 2: about += f"  {G['dot']}  ключ: {', '.join(st['only'])}"
    body.append(f"  {C.GY}{G['v']}{C.OFF} {about}")
    if note: body.append(f"  {C.GY}{G['v']}{C.OFF} {C.WH}«{note[:w - 8]}»{C.OFF}")
    body.append(f"  {C.GY}{G['v']} {hint}{C.OFF}")
    body += ["", f"  {C.GY}ЧТО БУДЕТ{C.OFF}"] + ["  " + l for l in textwrap.wrap(WIZ_TEXT[step], w - 20)] + [""]
    acts = wiz_actions(st, step)
    keyname = {"enter": "Enter", "left": G["larr"]}
    for i, (k, lab, _) in enumerate(acts):
        tag = f"[{keyname.get(k, k.upper())}]"
        if i == sel % len(acts):
            body.append("  " + C.INV + C.B + pad(f" {G['arrow']} {tag:8s} {lab}", w - 2) + C.OFF)
        else:
            body.append(f"     {C.YE}{tag:8s}{C.OFF} {C.WH}{lab}{C.OFF}")
    body += ["", "  " + C.GY + G["h"] * (w - 2) + C.OFF,
             f"  {C.GY}стрелки {G['dash']} выбор  {G['dot']}  Tab {G['dash']} всё меню целиком  {G['dot']}  "
             f"Q {G['dash']} выход{C.OFF}"]
    flush([clip(l, w + 2) for l in body])


def flush(body):
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
    """Scan whatever is new, let him pick the project from a list, then describe it with the job in mind.
    True when a project was chosen and described: that starts the step-by-step screen."""
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
    if cur.get("prefix") != prefix:          # another project: its script and video are not ours
        for k in ("keys", "script"): cur.pop(k, None)
    cur["prefix"] = prefix
    cur.setdefault("notes", {})[prefix] = note
    jsave(CURRENT, cur)
    cur["wizard"] = True                     # a new project: show it step by step until step 4 is done
    jsave(CURRENT, cur)
    print(f"\n  {C.GR}проект {prefix} описан. Дальше шаг 2 — написать скрипт.{C.OFF}")
    hold()
    return True


def step_write(st, secs=None):
    """The script, sized in seconds, written from the descriptions. Sets the file and the key for step 3.
    secs given: the step-by-step screen already knows the length, so don't ask again."""
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
    if not secs: secs = ask(f"  {C.WH}сколько секунд должен идти ролик [45] : {C.OFF}", "45")
    out = os.path.join(ROOT, "scripts", f"topics_{datetime.date.today():%m%d}.txt")
    before = set(keys_of(out)) if os.path.exists(out) else set()
    if run("script.py", "--only", prefix, "--seconds", secs, "--note", note, "--out", out, pause=False) != 0:
        hold(); return
    new = [k for k in keys_of(out) if k not in before]
    st["path"], st["keys"] = out, keys_of(out)
    st["only"] = new                                  # step 3 builds exactly what was just written
    cur["prefix"], cur["seconds"] = prefix, secs
    if new: cur["script"], cur["keys"], cur["script_at"] = out, new, int(time.time())   # followed by steps 3-4
    jsave(CURRENT, cur)
    print(f"\n  {C.GR}скрипт в scripts\\{os.path.basename(out)}" +
          (f", ключ: {', '.join(new)}" if new else "") + f"{C.OFF}")
    print(f"  {C.GY}прочитай его, поправь прямо в файле если надо, потом шаг 3.{C.OFF}")
    hold()
    return True


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
    if run("chrh.py", "sheet", *built, pause=False) == 0:
        cur = jload(CURRENT, {})
        cur.setdefault("checked", {}).update({k: time.time() for k in built})
        st["cur"] = cur
        if cur.get("wizard") and first_open(progress(st)[0]) is None:
            cur["wizard"] = False            # the project is finished: back to the whole menu
            print(f"\n  {C.GR}{C.B}проект {cur.get('prefix', '')} готов{C.OFF}{C.GR} — дальше общее меню{C.OFF}")
        jsave(CURRENT, cur)
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
    print(f"  {C.GY}{'ПРОЕКТ':26s}{'КЛИПОВ':9s}{'В РАБОТЕ':11s}ОПИСАНО{C.OFF}")
    for n, g in sorted(P.items(), key=lambda kv: -kv[1]["clips"]):
        col = C.GR if g["described"] >= g["on"] and g["on"] else (C.YE if g["described"] else C.GY)
        print(f"  {C.WH}{n[:25]:26s}{C.OFF}{g['clips']:<9d}{g['on']:<11d}{col}{g['described']}{C.OFF}")
    print(C.GY + "  " + G["h"] * W + C.OFF)
    nd = sum(g["on"] - g["described"] for g in P.values())
    if nd: print(f"  {C.YE}{nd} клип(ов) без описания — планировщик их не видит (пункт 7){C.OFF}")
    hold()


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


def wiz_act(ident, st):
    """The actions that exist only on the step-by-step screen."""
    cur = jload(CURRENT, {})
    prefix = cur.get("prefix", "")
    note = cur.get("notes", {}).get(prefix, "")
    if ident == "w_describe":
        run("describe.py", prefix, *(["--note", note] if note else []))
    elif ident == "w_note":
        if note: print(f"\n  {C.GY}сейчас: {note}{C.OFF}")
        new = ask(f"\n  {C.WH}пара слов о работе (пусто — оставить) : {C.OFF}")
        if not new: return
        cur.setdefault("notes", {})[prefix] = new
        jsave(CURRENT, cur)
        # the descriptions were written with the old note; redoing them costs a call per clip, so ask
        if ask(f"  {C.WH}описать клипы заново с новым описанием? [н] : {C.OFF}", "н").lower().startswith(("д", "y")):
            run("describe.py", "--force", prefix, "--note", new)
    elif ident == "w_seconds":
        secs = ask(f"\n  {C.WH}сколько секунд должен идти ролик [{cur.get('seconds', '45')}] : {C.OFF}",
                   cur.get("seconds", "45"))
        if secs.isdigit():
            cur["seconds"] = secs; jsave(CURRENT, cur)
            step_write(st, secs)
    elif ident == "w_write":
        step_write(st, cur.get("seconds", "45"))
    elif ident == "w_edit":
        f = cur.get("script") or st["path"]
        try:
            if os.name == "nt": subprocess.Popen(["notepad", f])
            else: subprocess.call(["xdg-open", f])
            print(f"\n  {C.GR}открыл {os.path.relpath(f, ROOT)}{C.OFF}  {C.GY}— сохрани и закрой, потом сборка{C.OFF}")
        except Exception as e:
            print(f"\n  {C.RE}не открылось: {e}{C.OFF}\n  {f}")
        hold()


def act(ident, st):
    if ident == "quit": return False
    elif ident.startswith("w_"): wiz_act(ident, st)
    elif ident == "look":
        if step_look(st): st["mode"], st["view"] = "b", None
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
      "work": work_size(), "cur": jload(CURRENT, {}), "view": None}
# Always start on the whole menu: reopening the half-done project on every launch got in the way. The project
# is not forgotten — the right panel names its step, and Tab goes back to it.
st["mode"] = "a"
sel, live = 0, True
if COLOUR: sys.stdout.write("\033[2J")


def follow_project(st):
    """On the step-by-step screen steps 3 and 4 work on the project's own script and key, whatever the
    whole-menu settings [F] and [K] say."""
    cur = st["cur"]
    if cur.get("script") and os.path.exists(cur["script"]) and cur.get("keys"):
        st["path"], st["keys"] = cur["script"], keys_of(cur["script"])
        st["only"] = [k for k in cur["keys"] if k in st["keys"]]


try:
    while live:
        st["cur"] = jload(CURRENT, {})
        if st["cur"].get("wizard") and first_open(progress(st)[0]) is None:
            st["cur"]["wizard"] = False      # finished by any route (also from the whole menu): back to A
            jsave(CURRENT, st["cur"])
        if not st["cur"].get("wizard"): st["mode"] = "a"
        wiz = st["mode"] == "b"
        if wiz:
            follow_project(st)
            step = wiz_step(st)[0]
            acts = wiz_actions(st, step)
            sel %= len(acts)
            draw_b(st, sel)
        else:
            sel %= len(RUNNABLE)
            draw_a(st, sel)
        keys_on()
        k = getkey()
        keys_off()                      # anything below here may print or ask a question
        if k is None:                   # a console that cannot read single keys: type the letter instead
            try: said = input(f"\n  {C.WH}{C.B}Выбор : {C.OFF}").strip().lower()
            except (EOFError, KeyboardInterrupt): break
            k = said[:1] if said else "enter"
            if said in ("q", "quit", "exit", "й"): k = "q"
            if said in ("tab", "таб"): k = "tab"
        if k == "\t": k = "tab"

        if k == "tab":
            if wiz: st["mode"], sel = "a", 0
            elif st["cur"].get("wizard"): st["mode"], sel, st["view"] = "b", 0, None
            continue
        if wiz:
            ident = None
            if k == "up": sel = (sel - 1) % len(acts)
            elif k == "down": sel = (sel + 1) % len(acts)
            elif k == "esc": st["mode"], sel = "a", 0
            elif k == "q": break
            elif k == "enter": ident = acts[sel][2]
            else:
                hit = [a for a in acts if a[0] == k]
                if hit: ident = hit[0][2]
            if ident == "w_back":
                st["view"], sel = step - 1, 0
            elif ident:
                if COLOUR: sys.stdout.write("\033[2J\033[H")
                live = act(ident, st)
                st["view"], sel = None, 0          # after any action show the step the project is really at
                st["keys"] = keys_of(st["path"])
                if COLOUR: sys.stdout.write("\033[2J")
            continue

        if k == "up": sel = (sel - 1) % len(RUNNABLE)
        elif k == "down": sel = (sel + 1) % len(RUNNABLE)
        elif k == "esc": break
        elif k == "enter" or k in BY_LETTER:
            if k in BY_LETTER: sel = BY_LETTER[k]
            if COLOUR: sys.stdout.write("\033[2J\033[H")
            live = act(RUNNABLE[sel][0], st)
            st["keys"] = keys_of(st["path"])
            if st["mode"] == "b": sel = 0
            if COLOUR: sys.stdout.write("\033[2J")
except KeyboardInterrupt:
    pass
finally:
    keys_off()

print(f"  {C.GY}пока{C.OFF}\n")
