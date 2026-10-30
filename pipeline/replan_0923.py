# Перепланировка 7 роликов 09-23: без уличной покраски, только резкие «живые» фрагменты.
# Выход: pipeline/plan_0923b.json  (P[key] = [(cut_word, clip, tin, speed, zoom), ...]) + отчёт.
import json, collections
import build, picker

NEW = ['hydraulics','storage','corrosion','welding','aluminum','shoptour','insideframe','rungear','whyblast','warranty']
KEEP = ['storage','shoptour','insideframe']

# --- тематические пулы (порядок = приоритет) ---
FIN   = ['5 car decking installed','5 car decking rear to back','5 car decking front to rear',
         '5 car decking above the tandem','5 car decking rear to the belly','DJI_20260920171423_0025_D']  # покрашенный трейлер В ЦЕХУ
SHOP  = ['DJI_20260920171423_0025_D','shop east to west','yard footage','DJI_20260920171458_0026_D']
HYDP  = ['video_2026-09-21_14-50-11','5 car decking rear to the belly','5 car decking above the tandem']
WELD  = ['сварка.','video_2026-09-21_14-50-04','video_2026-09-21_14-48-45','video_2026-09-21_14-48-40']
GRIND = ['video_2026-09-21_15-01-24','сварка.']
RUST  = ['зеркальная','video_2026-09-22_19-04-15','Car Hauler Storage Compartment Repair 2','Car Hauler Storage Compartment Repair.']
BLAST = ['пескоструй3','пескоструй.']       # пескоструй на улице — это НЕ покраска, трейлер в старой краске/голом металле
ALU   = ['video_2026-09-22_19-04-49','video_2026-09-22_19-03-53']
PRIM  = ['video_2026-09-21_14-48-45']          # грунт на новой косынке — в цеху
HUB   = ['video_2026-09-21_14-48-57','video_2026-09-21_14-50-11']
WORK  = ['video_2026-09-22_19-04-40','сварка.','video_2026-09-21_14-50-04']
ENCL  = ['video_2026-09-22_19-04-15','зеркальная']
TAND  = ['5 car decking above the tandem','5 car decking rear to the belly']
N = None
SLOTS = {
 'welding':   [(N,WELD),(11,['video_2026-09-21_14-50-04']+WELD),(16,['video_2026-09-21_14-48-40']+WELD),(23,WELD),
               (29,PRIM+WELD),(36,PRIM+WELD+FIN),(44,GRIND+WELD),(57,['video_2026-09-21_14-50-04']+WELD),(69,WELD+ALU),
               (84,['video_2026-09-21_14-48-40']+FIN),(100,WELD),(108,GRIND+WELD),(116,SHOP+FIN)],
 'whyblast':  [(N,BLAST),(13,BLAST),(16,RUST+GRIND),(25,RUST),(37,['пескоструй.','пескоструй3']),(46,PRIM+WELD),
               (57,GRIND+RUST),(81,BLAST),(90,FIN),(99,FIN),(105,SHOP+FIN)],
 'hydraulics':[(N,HYDP),(12,HYDP),(23,HYDP),(28,['video_2026-09-21_14-50-04']+HYDP),(37,HYDP),
               (44,['video_2026-09-21_14-50-04']+WELD),(59,WELD),(68,TAND+FIN),(83,FIN),(95,FIN),(110,SHOP+FIN)],
 'corrosion': [(N,RUST),(7,RUST),(18,ENCL+RUST),(27,RUST),(36,GRIND),(41,GRIND),(48,PRIM+WELD),(58,WELD),(69,RUST),
               (80,BLAST),(89,FIN),(95,RUST),(104,FIN),(109,SHOP+FIN)],
 'aluminum':  [(N,ALU),(7,ALU+FIN),(17,ALU+FIN),(23,ALU+WELD),(37,ALU+FIN),(44,ALU+FIN),(55,ALU+WELD),(62,WELD+ALU),(71,ALU+FIN),(83,FIN),(90,FIN),(100,SHOP+FIN)],
 'rungear':   [(N,TAND+FIN),(12,TAND),(21,HUB),(32,TAND+['video_2026-09-21_14-50-11']+FIN),(37,HUB+TAND+FIN),(43,HUB+WELD),
               (51,WORK+WELD),(61,WELD+GRIND),(79,['yard footage','shop east to west']+FIN),(99,FIN),(105,SHOP+FIN)],
 'warranty':  [(N,SHOP),(8,['DJI_20260920171423_0025_D','shop east to west']),(18,WORK),(30,SHOP+FIN),(36,FIN),(46,FIN),
               (52,ENCL),(56,['video_2026-09-21_14-50-11']+HYDP),(61,WELD),(66,WORK+SHOP),(79,GRIND+RUST),(85,GRIND+WELD),
               (89,WELD),(93,FIN),(100,SHOP+FIN),(104,SHOP+FIN)],
}
ORDER = ['welding','whyblast','hydraulics','corrosion','aluminum','rungear','warranty']

forbid = collections.defaultdict(list)       # вчерашняя партия 09-22 — жёстко
batch = collections.defaultdict(list)        # сегодняшняя партия — мягко (лучше не повторять)
for k in build.P:
    try: vo, total, segs = build.layout(k)
    except Exception: continue
    tgt = batch if k in KEEP else (forbid if k not in NEW else None)
    if tgt is None: continue
    for s in segs: tgt[s['file']].append((s['tin'], s['tin'] + s['n'] / 30 * s['sp']))

out = {}
for k in ORDER:
    slots = [(w, pool, None) for w, pool in SLOTS[k]]
    P, rep = picker.plan_video(k, slots, forbid, batch)
    out[k] = P
    print(k); print("\n".join(rep))
json.dump(out, open('plan_0923b.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
