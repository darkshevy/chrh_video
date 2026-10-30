# Shot plan for the 09-24 batch. Boss 09-24: wide shot OR close-up of welds/beams, action every 3-4 s
# (picker.split_long caps shots at 3.5 s), paint only indoors, only sharp "live" footage.
# Usage (after VO is aligned):  python replan_0924.py  -> plan_0924.json (loaded by plan.py)
import json, collections
import build, picker

WIDE  = ['DJI_20260920171423_0025_D', '5 car decking installed', '5 car decking rear to back',
         '5 car decking front to rear', '5 car decking above the tandem', '5 car decking rear to the belly']
CLOSE = ['video_2026-09-21_14-48-40', 'video_2026-09-21_14-48-45', 'video_2026-09-22_19-04-49',
         'сварка.', 'video_2026-09-21_14-50-04']                       # weld beads, gussets, beams
WELD  = ['сварка.', 'video_2026-09-21_14-50-04', 'video_2026-09-21_14-48-45']
HYD   = ['video_2026-09-21_14-50-11', '5 car decking rear to the belly', '5 car decking above the tandem']
YARD  = ['yard footage', 'shop east to west', 'DJI_20260920171458_0026_D']
WORK  = ['video_2026-09-22_19-04-40', 'сварка.', 'video_2026-09-21_14-50-04']
GRIND = ['video_2026-09-21_15-01-24', 'сварка.']
HUB   = ['video_2026-09-21_14-48-57', 'video_2026-09-21_14-50-11']
RUST  = ['зеркальная', 'video_2026-09-22_19-04-15']
N = None
SLOTS = {
 'deckdown':  [(N,HYD),(12,WIDE),(20,WIDE),(34,HYD),(39,HYD+WIDE),(47,WIDE),(54,HYD),(59,WIDE),(66,WELD),(72,CLOSE),
               (77,WIDE),(92,CLOSE),(96,HUB+CLOSE),(104,WIDE),(116,YARD+WIDE)],
 'sameday':   [(N,WIDE),(10,WIDE),(14,YARD+WIDE),(23,WORK),(38,WELD),(50,HYD),(61,WELD),(72,WIDE),(78,CLOSE),
               (88,WIDE),(101,WIDE),(111,YARD+WIDE)],
 'pricing':   [(N,RUST+CLOSE),(13,WIDE),(26,WORK),(40,YARD+WIDE),(52,WIDE),(61,WELD),(68,CLOSE),(75,WIDE),(83,WORK),
               (93,CLOSE),(108,WIDE),(118,YARD+WIDE)],
 'callfirst': [(N,WIDE),(10,WIDE),(24,WORK),(30,HYD),(42,YARD+WIDE),(55,WIDE),(63,WIDE),(73,CLOSE),(81,HYD),(86,WIDE),
               (96,WELD),(105,WORK),(115,WIDE)],
 'loaded':    [(N,WIDE),(10,WIDE),(25,WORK),(31,WELD),(42,WIDE),(54,YARD+WIDE),(64,WIDE),(70,YARD+WIDE),(83,RUST+CLOSE),
               (90,WIDE),(105,YARD+WIDE),(125,WIDE)],
 'bays':      [(N,YARD+WIDE),(7,WIDE),(13,WIDE),(29,WIDE),(43,YARD+WIDE),(58,YARD+WIDE),(66,WIDE),(73,WIDE),(79,WIDE),
               (91,WIDE),(97,YARD+WIDE),(108,WIDE)],
 'reviews':   [(N,WIDE),(14,WELD),(22,CLOSE),(27,CLOSE),(39,WIDE),(45,WIDE),(54,CLOSE),(63,WIDE),(69,WORK),(80,WIDE),
               (89,YARD+WIDE),(105,WIDE)],
 'fleet':     [(N,YARD+WIDE),(7,WIDE),(20,WORK),(33,WIDE),(47,CLOSE),(58,WELD),(69,WIDE),(75,CLOSE),(88,WORK),(94,WELD),
               (101,YARD+WIDE),(115,WIDE)],
 'warranty6': [(N,CLOSE),(7,WIDE),(12,WELD),(24,CLOSE),(30,WIDE),(38,WIDE),(51,WIDE),(56,YARD+WIDE),(64,RUST+CLOSE),
               (76,WORK),(83,CLOSE),(97,WIDE),(102,WELD),(114,WIDE)],
 'cottrell':  [(N,WIDE),(3,CLOSE),(13,WIDE),(19,GRIND+CLOSE),(35,WIDE),(41,WIDE),(50,WIDE),(55,WORK),(64,WELD),(68,WIDE),
               (83,WIDE),(92,CLOSE),(103,HYD),(110,WIDE),(114,YARD+WIDE)],
}

if __name__ == "__main__":
    # everything shown before (all days) is "soft used": the picker prefers fresh seconds, but may reuse if needed
    soft = collections.defaultdict(list)
    for k in build.P:
        if k in SLOTS: continue
        try: vo, total, segs = build.layout(k)
        except Exception: continue
        for s in segs: soft[s['file']].append((s['tin'], s['tin'] + s['n'] / 30 * s['sp']))
    out = {}
    for k, sl in SLOTS.items():
        if str(k) not in build.A: print(k, "— no alignment yet, skipped"); continue
        P, rep = picker.plan_video(k, [(w, pool, None) for w, pool in sl], {}, soft)
        out[k] = P; print(k); print("\n".join(rep))
    json.dump(out, open('plan_0924.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
