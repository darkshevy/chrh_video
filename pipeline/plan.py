import os
# segments: (cut_word_index or None for start, clip_prefix, in_point, speed, zoom)
# zoom: None or (z, cx, cy)
Z=(1.3,0.5,0.38)
P={}
P[1]=[(None,"D867",0.5,1,None),(8,"1D59",11.5,1,None),(14,"415B",1.0,1,None),(20,"A755",1.5,1,None),
 (25,"video_2026-09-21_14-48-40",14.5,1,None),(30,"23BE",1.0,1,None),(36,"0A2F",1.5,1,None),
 (43,"video_2026-09-21_14-48-57",0.8,1,None),(52,"89A7",5.0,1,None),(57,"7080",1.0,1,None),(62,"3050",0.5,1,None),
 (65,"D867",7.0,1,None),(70,"2E5A",2.0,1,None),(77,"video_2026-09-21_14-49-39",9.5,1,None),
 (85,"video_2026-09-21_14-50-04",3.8,1,None),(88,"video_2026-09-21_14-48-20",2.0,0.5,None),
 (91,"пескоструй2",3.0,1,Z),(92,"покраска.",20.0,1,None),(95,"video_2026-09-21_14-58-40",10.0,1,None)]
P[2]=[(None,"1D59",2.0,1,None),(7,"video_2026-09-21_14-50-04",3.0,1,None),(13,"video_2026-09-21_14-48-40",2.0,1,None),
 (21,"video_2026-09-21_14-48-57",4.5,1,None),(28,"0C4A",4.0,1,None),(36,"7080",3.0,1,None),
 (44,"video_2026-09-21_14-48-45",0.5,1,None),(50,"B4C6",2.0,1,None),(54,"video_2026-09-21_14-50-04",6.5,1,None),
 (58,"BD5E",0.1,1,None),(62,"D390",0.3,1,None),(70,"покраска2",1.0,1,None),(75,"2E5A",3.5,1,None),
 (83,"video_2026-09-21_14-48-45",2.6,1,None),(89,"D867",4.0,1,None),(93,"video_2026-09-21_14-49-39",10.5,1,None)]
P[3]=[(None,"video_2026-09-21_14-48-45",1.2,1,None),(10,"23BE",4.0,1,None),(19,"6553",1.0,1,None),
 (22,"23BE",6.5,1,None),(34,"video_2026-09-21_14-48-17",0.2,1,None),(42,"video_2026-09-21_14-49-46",0.3,1,None),
 (49,"video_2026-09-21_14-48-20",1.0,0.5,None),(57,"video_2026-09-21_14-48-24",0.5,1,None),
 (62,"IMG_0083",3.0,1,None),(70,"video_2026-09-21_14-48-26",0.8,1,None),(77,"video_2026-09-21_14-58-29",16.0,1,None),
 (88,"video_2026-09-21_14-48-20",5.0,0.5,None),(97,"пескоструй.",2.0,1,None)]
P[4]=[(None,"video_2026-09-21_14-48-45",0.2,1,None),(11,"пескоструй2",1.0,1,Z),(17,"пескоструй3",1.0,1,Z),
 (22,"video_2026-09-21_14-48-40",14.0,1,None),(26,"пескоструй.",5.0,1,None),(31,"video_2026-09-21_14-50-11",6.0,1,None),
 (36,"video_2026-09-21_14-49-39",1.0,1,None),(44,"покраска.",8.0,1,None),(50,"покраска2",0.5,1,None),
 (57,"video_2026-09-21_14-59-44",5.0,1,None),(64,"video_2026-09-21_14-58-29",5.0,1,None),(71,"покраска.",22.0,1,None),
 (80,"video_2026-09-21_14-58-29",25.0,1,None),(84,"video_2026-09-21_14-49-08",3.0,1,None),(91,"video_2026-09-21_14-58-40",25.0,1,None)]
P[5]=[(None,"video_2026-09-21_14-49-08",8.0,1,None),(9,"video_2026-09-21_14-58-40",3.0,1,None),
 (17,"video_2026-09-21_14-59-44",7.0,1,None),(26,"video_2026-09-21_14-49-30",0.3,1,None),(31,"IMG_0331",5.0,1,None),
 (37,"video_2026-09-21_14-49-30",2.8,1,None),(42,"415B",3.0,1,None),(49,"0A2F",6.0,1,None),
 (51,"video_2026-09-21_14-50-04",1.0,1,None),(54,"video_2026-09-21_14-48-20",4.0,0.5,None),(56,"пескоструй2",8.0,1,Z),
 (57,"покраска2",12.0,1,None),(60,"video_2026-09-21_14-49-39",11.0,1,None),(65,"IMG_0331",20.0,1,None),
 (74,"IMG_0331",35.0,1,None),(83,"video_2026-09-21_14-58-40",18.0,1,None),(87,"video_2026-09-21_14-58-40",33.0,1,None)]
TITLE={1:"THE ARRIVAL",2:"STRUCTURAL WELDING",3:"NEW DECKS",4:"SANDBLAST & PAINT",5:"READY FOR WORK"}
NEXT={1:"Part 2 next: structural welding",2:"Part 3 next: new decks",3:"Part 4 next: sandblast & paint",4:"Part 5 next: ready for work",5:None}

# ===== v2: red trailer only =====
P[1]=[(None,"D867",0.5,1,None),(8,"1D59",11.5,1,None),(14,"415B",1.0,1,None),(20,"A755",1.5,1,None),
 (25,"7ED4",1.0,1,None),(30,"23BE",1.0,1,None),(36,"0A2F",1.5,1,None),
 (43,"0C4A",1.0,1,None),(52,"89A7",5.0,1,None),(57,"7080",1.0,1,None),(62,"3050",0.5,1,None),
 (65,"D867",7.0,1,None),(70,"2E5A",2.0,1,None),(77,"video_2026-09-21_14-49-08",3.0,1,None),
 (85,"B4C6",2.0,1,None),(88,"IMG_0083",1.0,1,None),
 (91,"пескоструй2",3.0,1,Z),(92,"покраска.",20.0,1,None),(95,"video_2026-09-21_14-58-40",10.0,1,None)]
P[2]=[(None,"D867",0.5,1,None),(7,"2E5A",0.5,1,None),(13,"0A2F",1.5,1,None),(21,"8F1A",1.0,1,None),
 (28,"0C4A",4.0,1,None),(36,"7080",3.0,1,None),(44,"1D59",11.5,1,None),(50,"89A7",5.0,1,None),
 (54,"B4C6",2.0,1,None),(58,"BD5E",0.1,1,None),(62,"D390",0.3,1,None),(70,"покраска2",1.0,1,None),
 (75,"2E5A",3.5,1,None),(83,"video_2026-09-21_14-49-08",10.0,1,None),(89,"7ED4",1.0,1,None),(93,"IMG_0331",20.0,1,None)]
P[3]=[(None,"6553",0.5,1,None),(10,"23BE",1.0,1,None),(19,"6553",4.5,1,None),(22,"23BE",6.0,1,None),
 (34,"IMG_0083",0.5,1,None),(42,"IMG_0083",6.0,1,None),(49,"IMG_0331",23.0,1,None),(57,"покраска.",27.5,1,None),
 (62,"video_2026-09-21_14-48-20",1.0,0.5,None),(70,"video_2026-09-21_14-48-26",0.8,1,None),
 (77,"video_2026-09-21_14-58-29",0.3,1,None),(88,"пескоструй.",2.0,1,None),(97,"IMG_0331",30.0,1,None)]
P[5]=[(None,"video_2026-09-21_14-49-08",8.0,1,None),(9,"video_2026-09-21_14-58-40",3.0,1,None),
 (17,"video_2026-09-21_14-59-44",7.0,1,None),(26,"IMG_0331",5.0,1,None),(31,"video_2026-09-21_14-49-08",20.0,1,None),
 (37,"video_2026-09-21_14-59-44",10.5,1,None),(42,"415B",3.0,1,None),(49,"0A2F",6.0,1,None),(51,"B4C6",3.0,1,None),
 (54,"IMG_0083",3.0,1,None),(56,"пескоструй2",8.0,1,Z),(57,"покраска.",19.0,1,None),
 (60,"video_2026-09-21_14-58-40",10.0,1,None),(65,"IMG_0331",35.0,1,None),(74,"video_2026-09-21_14-49-08",30.0,1,None),
 (83,"video_2026-09-21_14-58-40",18.0,1,None),(87,"video_2026-09-21_14-58-40",33.0,1,None)]

# ===== Part 4 v2 (new VO, red trailer + drone) =====
DC=(1.0,0.5,0.5)
P[4]=[(None,"DJI_20260920171217_0022_D",1.0,1,DC),(9,"пескоструй2",0.5,1,Z),(16,"пескоструй3",1.0,1,Z),
 (26,"пескоструй2",8.5,1,Z),(30,"0A2F",7.0,1,None),(34,"пескоструй2",10.0,1,Z),
 (44,"пескоструй.",1.0,1,None),(49,"пескоструй.",8.0,1,None),(55,"покраска.",29.0,1,None),
 (60,"покраска.",17.0,1,None),(64,"покраска.",20.0,1,None),(73,"покраска.",23.0,1,None),
 (83,"покраска2",0.5,1,None),(91,"DJI_20260920171058_0020_D",1.5,1,DC),(100,"DJI_20260920171321_0023_D.mp4",1.0,1,DC),
 (107,"DJI_20260920171021_0019_D",0.8,1,DC)]
TITLE[4]="SANDBLAST, PRIMER & PAINT"

# ===== Decks — general, service-wide (VO: voiceover/decks.mp3) =====
# drone clips are 16:9 -> z=(1, cx, 0.5) picks the horizontal window of the 9:16 crop
def D(cx): return (1.0,cx,0.5)
P["decks"]=[(None,"yard footage",0.5,1,D(0.45)),          # At CHRH
 (5,"shop east to west",11.5,1,D(0.5)),                   # deck work is a big part of what we do
  (15,"23BE",0.3,0.8,None),                                 # Decks take more abuse (worn, patched deck)
 (28,"6553",5.4,1,None),                                   # every vehicle loaded and unloaded
 (35,"video_2026-09-21_14-48-24",0.0,1,None),              # wears them down a little more
 (41,"6553",0.8,1,None),                                   # Damaged decks slow down loading
 (47,"5 car decking rear to the belly",13.0,1,D(0.5)),     # put the cars you haul at risk
 (54,"video_2026-09-21_14-48-20",1.4,0.5,None),            # pays to fix them before they fail (weld bead)
 (63,"IMG_0083",0.3,1,None),                               # We repair damaged decks
 (67,"5 car decking installed",12.3,1,D(0.55)),            # and build new ones in our shop
 (74,"5 car decking front to rear",9.0,1,D(0.5)),          # both steel
 (78,"video_2026-09-21_14-48-17",0.8,1,None),              # and aluminum
 (80,"IMG_0083",6.1,1,None),                               # perforated deck sections
 (84,"5 car decking front to rear",0.7,1,D(0.5)),          # complete deck replacements
 (88,"video_2026-09-21_14-48-26",0.2,1,None),              # right now we're also building
 (93,"video_2026-09-21_14-48-20",5.2,1,None),              # aluminum ramps
 (96,"video_2026-09-21_14-49-46",0.1,1,None),              # Whatever style your trailer runs
 (101,"5 car decking above the tandem",4.8,1,D(0.5)),      # we build decks to fit it
 (107,"5 car decking installed",18.1,1,D(0.5)),            # Want to see more of our deck work?
 (115,"yard footage",12.9,1,D(0.4))]                       # Check out our page / contact + end card
TITLE["decks"]="DECKS"; SUB={"decks":"REPAIR & NEW BUILDS"}; NEXT["decks"]=None

# ===== Miller 2007 7-car — bushings & hinges (VO: voiceover/miller.mp3) =====
# one trailer only: old shop batch 464x848. A755 == 8F1A (duplicate clip). BD5E/D390 (gussets) not in script -> unused.
P["miller"]=[(None,"D867",0.4,1,None),         # This 2007 Miller seven-car hauler (wide: pivot arms + platform)
 (8,"0C4A",0.3,1,None),                         # came into CHRH with
 (15,"415B",0.3,1,None),                        # worn-out hinge points (rusted ear, wallowed hole)
 (19,"B4C6",0.3,1,None),                        # The bushings were broken (cracked block around bushing)
 (23,"8F1A",0.2,1,None),                        # several hinges worn far past service life
 (32,"23BE",0.3,0.8,None),                      # platform was badly damaged
 (38,"7080",3.3,1,None),                        # no longer operated the way it should (worn bushing flange)
 (47,"2E5A",0.2,1,None),                        # Our team replaced the bushings (new bushing plate clamped, torch)
 (52,"1D59",0.5,1,None),                        # partially replaced the hinges (new welded hinge plates)
 (63,"612C",0.2,1,None),                        # restoring the pivot points (bushing plate welded in)
 (67,"89A7",0.4,1,None),                        # every platform movement depends on (hinge + pin assembled)
 (73,"3050",0.1,1,None),                        # Worn bushings and hinges don't fix themselves
 (80,"0A2F",9.8,1,None),                        # the longer they're ignored (torn ear)
 (85,"6553",5.4,1,None),                        # the more damage ... rest of the trailer (damaged deck on frame)
 (96,"7ED4",2.3,1,None),                        # Now this Miller's platform (new hinge welded, pin)
 (101,"89A7",5.1,1,None),                       # is ready to work correctly again
 (106,"612C",3.5,1,None),                       # Need hinge or bushing repair?
 (111,"1D59",8.5,1,None)]                       # Contact CHRH + end card
TITLE["miller"]="2007 MILLER"; SUB["miller"]="BUSHINGS & HINGES"; NEXT["miller"]=None

# music per video: (file in music/, on-screen credit). Artist verified on SoundCloud: soundcloud.com/dj-koz-love
DJ="DJ KOZ LOVE"
TRACK={"decks":("Thunder.mp3",f"{DJ}  ·  Thunder"),"miller":("Thunder.mp3",f"{DJ}  ·  Thunder")}

# ===== Sandblast & paint — red trailer only (VO: voiceover/sandblast.mp3) =====
# boss order: blasting (worker, dust) -> gray bare steel -> [masking] -> brown primer -> red top coat. 14-50-11 = black trailer, excluded.
ZB=(1.3,0.5,0.38)
P["sandblast"]=[(None,"пескоструй2",0.4,1,ZB),           # Sandblasting is one of the most demanding jobs
 (10,"пескоструй3",0.3,1,ZB),                             # at CHRH
 (15,"пескоструй2",4.0,1,ZB),                             # the step that decides how long the paint job lasts
 (27,"пескоструй2",8.0,1,None),                           # Before blasting, the trailer is fully prepared (old red paint)
 (34,"пескоструй2",11.0,1,ZB),                            # Then our team blasts the entire frame
 (41,"пескоструй.",4.5,1,None),                           # cutting through old paint and rust (nozzle, rust vs blasted)
 (47,"покраска.",1.0,1,None),                             # down to bare gray steel
 (57,"покраска2",12.0,1,None),                            # ready for the next stage (gray)
 (62,"video_2026-09-21_14-59-44",0.3,1,None),             # every element that needs protection (gray only, no red in frame)
 (69,"покраска.",7.3,1,None),                             # masked and taped (gray) -- no real masking shot yet
 (72,"video_2026-09-21_14-49-39",3.0,1,None),             # trailer gets a coat of brown primer (spraying on gray)
 (81,"покраска.",17.0,1,None),                            # to seal the fresh metal (brown primer)
 (86,"покраска2",0.5,1,None),                             # final stage: red top coat
 (94,"IMG_0331",13.0,1,None),                             # laid over the primer, clean durable finish
 (103,"IMG_0331",38.0,1,None),                            # Paint can only be as good as the surface
 (114,"DJI_20260920171058_0020_D",8.0,1,(1.0,0.5,0.5))]   # Contact CHRH (drone fly-through finished trailer) + end card
TITLE["sandblast"]="SANDBLAST & PAINT"; SUB["sandblast"]="BARE STEEL TO TOP COAT"; NEXT["sandblast"]=None
TRACK["sandblast"]=("Thunder.mp3",f"{DJ}  ·  Thunder")

# ===== Paint & primer series 2026-09-22 (scripts/paint_series_0922.txt) — shot lists added after VO arrives =====
for _k,_t in {"fullrefinish":"Hollywood waves","primer":"Fields of space","topcoat":"Kama Sutra",
              "nonskid":"Another Day","fromabove":"Symphony one","overview":"Hyde and seek"}.items():
    TRACK[_k]=(f"{_t}.mp3",f"{DJ}  ·  {_t}")

# ----- shot lists, paint series 09-22. Stage map (verified on contact sheets 09-22):
#   blast: пескоструй2/3 (ZB), пескоструй. 4-9 (nozzle/rust)
#   GRAY only: покраска 0-13, покраска2 12.5-19.6, 14-49-39 0-4.3 (spraying gray frame 2.4-4.3), 14-59-44 0-5
#   PRIMER (brown/maroon): покраска 16.3-25     !! 14-49-39 >4.5 and покраска2 5-12 = red+gray mixed -> never used
#   RED: покраска2 0-5, IMG_0331, 14-49-08, 14-58-40, drones 0018-0024
#   NON-SKID (after red): tape 19-07-16, 19-07-22; roller 19-07-05 3-5.4, 19-07-11; texture 19-07-08, 19-07-02
V="video_2026-09-21_"; N="video_2026-09-22_"
P["fullrefinish"]=[(None,"пескоструй2",0.4,1,ZB),(15,"пескоструй3",0.3,1,ZB),(25,"пескоструй2",4.0,1,ZB),
 (31,"пескоструй.",4.5,1,None),(36,"пескоструй2",11.0,1,ZB),(40,"покраска.",1.0,1,None),(47,"покраска2",13.0,1,None),
 (55,V+"14-49-39",1.8,0.7,None),(61,"покраска.",17.0,1,None),(70,"покраска2",0.5,1,None),(78,"IMG_0331",13.0,1,None),
 (82,N+"19-07-11",0.5,1,None),(89,N+"19-07-08",0.3,1,None),(92,V+"14-58-40",22.5,1,None),
 (102,"DJI_20260920171133_0021_D",0.3,1,D(0.5)),(115,"DJI_20260920171021_0019_D",0.4,1,D(0.5))]
P["primer"]=[(None,"пескоструй2",0.4,1,ZB),(20,"пескоструй3",0.3,1,ZB),(28,"покраска.",1.0,1,None),
 (34,"покраска2",13.0,1,None),(44,V+"14-49-39",2.0,0.8,None),
 (52,"покраска.",16.3,0.65,None),(56,"покраска.",17.8,0.65,None),(63,"покраска.",19.5,0.65,None),
 (73,"покраска.",21.6,0.65,None),(81,"покраска.",23.6,0.65,None),
 (86,"покраска2",0.5,1,None),(98,"IMG_0331",13.0,1,None),(108,"DJI_20260920171058_0020_D",8.0,1,D(0.5))]
P["topcoat"]=[(None,"DJI_20260920170925_0018_D",0.5,1,D(0.3)),(9,V+"14-58-40",1.0,1,None),(13,"покраска2",0.5,1,None),
 (21,"IMG_0331",38.0,1,None),(26,V+"14-58-40",11.0,1,None),(37,"IMG_0331",13.0,1,None),(46,V+"14-49-08",3.0,1,None),
 (56,"DJI_20260920171133_0021_D",0.3,1,D(0.5)),(69,V+"14-58-40",22.5,1,None),(81,"покраска2",2.8,1,None),
 (90,"DJI_20260920171021_0019_D",0.4,1,D(0.5)),(99,"DJI_20260920171058_0020_D",8.0,1,D(0.5))]
P["nonskid"]=[(None,"Fresh paint",4.0,0.8,None),(12,"Fresh paint",6.8,0.8,None),(18,N+"19-07-16",0.3,1,None),
 (29,N+"19-07-22",0.3,1,None),(40,N+"19-07-11",0.1,1,None),(50,N+"19-07-05",3.4,1,None),(55,N+"19-07-11",2.4,1,None),
 (63,N+"19-07-22",4.3,1,None),(69,N+"19-07-08",0.2,1,None),(77,N+"19-07-02",0.2,1,None),(83,N+"19-07-02",3.0,1,None),
 (92,N+"19-07-08",2.5,1,None),(98,N+"19-06-53",2.0,1,None),(113,N+"19-06-53",15.0,1,None)]
P["fromabove"]=[(None,"DJI_20260920170925_0018_D",0.5,1,D(0.3)),(13,"DJI_20260920171021_0019_D",0.4,1,D(0.5)),
 (26,"DJI_20260920171133_0021_D",0.3,1,D(0.5)),(38,"DJI_20260920171343_0024_D",0.2,1,D(0.5)),
 (50,"DJI_20260920171058_0020_D",1.5,1,D(0.5)),(66,"DJI_20260920170925_0018_D",21.0,1,D(0.3)),
 (77,"IMG_0331",35.0,1,None),(85,V+"14-58-40",11.0,1,None),(93,"DJI_20260920171321_0023_D.mp4",1.0,1,D(0.5)),
 (104,"DJI_20260920171458_0026_D",15.6,1,D(0.5)),(113,"DJI_20260920171021_0019_D",6.0,1,D(0.5))]
P["overview"]=[(None,"yard footage",0.5,1,D(0.45)),(17,"сварка.",11.5,1,None),(29,V+"14-50-04",3.0,1,None),
 (36,N+"19-04-49",9.5,1,None),(46,N+"19-03-53",0.3,1,None),(52,"5 car decking installed",12.3,1,D(0.55)),
 (55,V+"14-50-11",6.0,1,None),(67,V+"14-49-30",0.2,1,None),(75,"пескоструй2",0.4,1,ZB),(81,"покраска.",17.5,1,None),
 (83,"покраска2",0.5,1,None),(84,"shop east to west",11.5,1,D(0.5)),(90,"D867",0.4,1,None),(95,"0C4A",0.3,1,None),
 (98,"DJI_20260920171458_0026_D",0.5,1,D(0.5)),(106,"yard footage",12.9,1,D(0.4))]
TITLE.update(fullrefinish="FULL REFINISH",primer="PRIMER",topcoat="TOP COAT",nonskid="NON-SKID",fromabove="FROM ABOVE",overview="ONE SHOP")
SUB.update(fullrefinish="STRIP · PRIME · PAINT",primer="THE COAT YOU DON'T SEE",topcoat="THE FINISH",
           nonskid="THE FINAL DETAIL",fromabove="RESTORED & READY",overview="EVERYTHING UNDER ONE ROOF")
for _k in P:
    if isinstance(_k,str): NEXT.setdefault(_k,None)

# manual blur boxes (final 1080x1920 coords): key -> [(t0,t1,x,y,w,h)] for faces the detector misses
BLUR={}

# ===== 10 topics 2026-09-23 — only ranges unused by the 09-22 batch (verified by check_ranges) =====
SC="Car Hauler Storage Compartment Repair"
# 19-03-53 after 5 s and 14-50-11 15-19 are soft/bench-floor pans -> drone + finished trailer instead
P["hydraulics"]=[(None,V+"14-50-11",0.2,1,None),(12,V+"14-50-11",11.0,1,None),(23,V+"14-50-11",3.0,0.85,None),
 (28,V+"14-50-11",15.0,0.9,None),(37,V+"14-50-11",14.9,1,None),(44,"DJI_20260920171133_0021_D",4.9,1,D(0.5)),
 (59,"DJI_20260920171133_0021_D",8.0,1,D(0.5)),(68,"DJI_20260920170925_0018_D",6.0,1,D(0.3)),
 (83,"DJI_20260920170925_0018_D",10.5,1,D(0.3)),(95,"DJI_20260920170925_0018_D",14.5,1,D(0.25)),
 (110,V+"14-58-40",27.0,1,None)]
P["storage"]=[(None,SC+".",0.5,1,None),(14,SC+".",6.0,1,None),(25,SC+" 2",1.0,1,None),(37,SC+" 2",5.0,1,None),
 (52,N+"19-04-40",0.4,1,None),(63,N+"19-04-40",4.5,1,None),(75,SC+" 2",11.0,1,None),(84,SC+".",10.5,1,None),
 (97,SC+" 2",15.5,1,None),(107,SC+" 2",20.0,1,None)]
P["corrosion"]=[(None,"зеркальная",0.3,1,None),(7,"зеркальная",2.4,1,None),(18,N+"19-04-15",5.0,1,None),
 (27,N+"19-04-15",8.0,1,None),(36,V+"15-01-24",0.2,1,None),(41,V+"15-01-24",2.3,0.75,None),
 (48,N+"19-04-15",12.0,1,None),(58,"зеркальная",5.5,1,None),(69,N+"19-04-15",0.3,1,None),
 (80,"пескоструй3",3.3,0.8,ZB),(95,"пескоструй3",5.8,0.85,ZB),(104,"покраска.",25.5,0.9,None)]
P["welding"]=[(None,"сварка.",0.5,1,None),(11,V+"14-50-04",0.2,1,None),(16,V+"14-48-40",0.5,1,None),
 (23,V+"14-48-40",3.0,1,None),(29,V+"14-48-45",0.2,1,None),(36,V+"14-48-45",2.4,0.55,None),
 (44,"сварка.",3.5,1,None),(57,V+"14-50-04",5.8,1,None),(69,"сварка.",7.2,1,None),(84,V+"14-48-40",12.0,1,None),
 (100,V+"14-48-40",6.5,1,None),(108,V+"14-48-40",9.0,1,None),(116,"сварка.",6.5,0.85,None)]
P["aluminum"]=[(None,N+"19-04-49",0.5,1,None),(17,V+"14-48-26",1.8,0.6,None),(23,N+"19-04-49",4.2,0.9,None),
 (37,N+"19-03-53",3.9,1,None),(55,N+"19-03-53",9.8,1,None),(71,N+"19-04-49",14.0,1,None),
 (83,V+"14-48-20",2.7,0.7,None),(90,N+"19-03-53",6.0,1,None),(100,"5 car decking installed",20.0,1,D(0.5))]
P["shoptour"]=[(None,"DJI_20260920171423_0025",0.5,1,D(0.5)),(21,"DJI_20260920171423_0025",7.0,1,D(0.5)),
 (24,"DJI_20260920171423_0025",9.0,1,D(0.5)),(33,"DJI_20260920171423_0025",12.5,1,D(0.5)),
 (44,"DJI_20260920171458_0026",4.0,1,D(0.5)),(61,"shop east to west",0.5,1,D(0.5)),
 (77,"shop east to west",6.0,1,D(0.5)),(89,"DJI_20260920171423_0025",17.0,1,D(0.5)),
 (105,"yard footage",7.4,1,D(0.4))]
P["insideframe"]=[(None,"5 car decking rear to back",0.5,1,D(0.5)),(12,"5 car decking rear to back",5.0,1,D(0.5)),
 (24,"5 car decking rear to back",10.0,1,D(0.5)),(37,"5 car decking front to rear",11.0,1,D(0.5)),
 (56,"5 car decking rear to the belly",1.0,1,D(0.5)),(71,"5 car decking above the tandem",7.0,1,D(0.5)),
 (77,"5 car decking rear to the belly",6.0,1,D(0.5)),(91,"5 car decking front to rear",18.0,1,D(0.5)),
 (101,"5 car decking rear to back",20.0,1,D(0.5)),(108,"5 car decking front to rear",20.5,0.95,D(0.5))]
P["rungear"]=[(None,V+"14-48-57",0.3,1,None),(12,V+"14-59-44",3.0,1,None),(21,V+"14-48-57",3.5,1,None),
 (32,V+"14-59-44",6.0,1,None),(37,V+"14-59-44",10.0,0.85,None),(43,V+"14-48-57",5.5,0.7,None),
 (51,V+"14-59-44",8.2,0.7,None),(79,V+"14-48-57",0.5,0.75,None),(99,"DJI_20260920170925_0018_D",6.0,1,D(0.3)),
 (105,"DJI_20260920170925_0018_D",13.0,1,D(0.3))]
P["whyblast"]=[(None,"пескоструй.",6.8,1,None),(13,"пескоструй.",10.5,1,None),(16,"пескоструй.",12.0,1,None),
 (25,"пескоструй.",15.2,0.75,None),(37,V+"14-58-29",2.0,1,None),(46,V+"14-58-29",9.0,1,None),
 (57,V+"14-58-29",13.0,1,None),(81,V+"14-58-29",20.0,1,None),(99,"покраска.",25.0,1,None),
 (105,"покраска.",27.0,0.9,None)]
# warranty: 0026 past 12 s is sky only -> open on the yard at 9.6
P["warranty"]=[(None,"DJI_20260920171458_0026",9.6,1,D(0.5)),(8,"DJI_20260920171423_0025",20.5,1,D(0.5)),
 (18,"1D59",3.8,1,None),(25,"0A2F",0.5,1,None),(36,"B4C6",2.0,1,None),(42,"D867",3.6,1,None),
 (48,"89A7",7.0,1,None),(56,"23BE",3.2,1,None),(66,"0C4A",2.6,1,None),(79,"0A2F",4.5,1,None),
 (85,"D867",6.6,1,None),(100,"1D59",13.8,1,None),(104,"shop east to west",14.0,1,D(0.5))]
TITLE.update(hydraulics="HYDRAULICS",storage="STORAGE COMPARTMENTS",corrosion="CORROSION",welding="STRUCTURAL WELDING",
 aluminum="ALUMINUM WORK",shoptour="INSIDE THE SHOP",insideframe="UNDER THE DECKS",rungear="RUNNING GEAR",
 whyblast="WHY BLASTING",warranty="COTTRELL CERTIFIED")
SUB.update(hydraulics="CYLINDERS, LINES & PUMPS",storage="REBUILT FROM THE FRAME UP",corrosion="CUT IT OUT, BUILD IT BACK",
 welding="WHERE THE LOAD GOES",aluminum="RAMPS, DECKS, SECTIONS",shoptour="EVERYTHING IN ONE PLACE",
 insideframe="A 5-CAR FROM THE INSIDE",rungear="HUBS, SPRINGS, BRAKES, TIRES",whyblast="THE SURFACE DECIDES",
 warranty="WARRANTY WORK IN HOUSTON")
for _k,_t in {"hydraulics":"Kama Sutra","storage":"Another Day","corrosion":"Fields of space","welding":"Thunder",
              "aluminum":"Hollywood waves","shoptour":"Symphony one","insideframe":"Hyde and seek",
              "rungear":"Kama Sutra","whyblast":"Another Day","warranty":"Thunder"}.items():
    TRACK[_k]=(f"{_t}.mp3",f"{DJ}  ·  {_t}"); NEXT.setdefault(_k,None)

# clips that can show a human face — only these are scanned for blurring (boss rule 7).
# everything else (hubs, hinge holes, bolt heads) used to trigger false positives.
PEOPLE=("сварка.","14-50-04","14-49-30","15-01-24","19-04-40","Storage Compartment",
        "14-49-39","покраска.","пескоструй","19-07-","19-04-15","19-03-53","1D59","14-59-44")

# ===== 09-23 re-cut (boss/David): no outdoor painting on screen, only sharp "live" footage =====
# Picked by replan_0923.py + picker.py (sharpness/motion measured on source, pools per phrase).
import json as _json, os as _os
from paths import PIPE as _PIPE
_rp = _os.path.join(_PIPE, "plan_0923b.json")
if _os.path.exists(_rp):
    for _k, _segs in _json.load(open(_rp, encoding="utf-8")).items():
        P[_k] = [(w, f, t, sp, tuple(z) if z else None) for w, f, t, sp, z in _segs]

# partner logo overlays: key -> (png, spoken word that triggers it, width px). Cottrell logo = vector from cottrelltrailers.com
LOGO={"cottrell":(os.path.join(_PIPE,"assets","cottrell_logo.png"),"cottrell",420)}

# ===== 09-24 batch: shot lists from replan_0924.py (same loader as 09-23) =====
_rp = _os.path.join(_PIPE, "plan_0924.json")
if _os.path.exists(_rp):
    for _k, _segs in _json.load(open(_rp, encoding="utf-8")).items():
        P[_k] = [(w, f, t, sp, tuple(z) if z else None) for w, f, t, sp, z in _segs]
TITLE.update(deckdown="DECK DOWN?", sameday="SAME DAY", pricing="$0 TO LOOK", callfirst="60 SECONDS",
             loaded="STILL LOADED?", bays="FOUR BAYS", reviews="FIVE STARS", fleet="RUNNING A FLEET?",
             warranty6="6-MONTH WARRANTY", cottrell="COTTRELL AUTHORIZED")
SUB.update(deckdown="IF IT'S ON A CARRIER, WE FIX IT", sameday="ONE DAY HERE. A WEEK THERE.",
           pricing="PRICE BEFORE THE WRENCH", callfirst="CALL BEFORE YOU DRIVE", loaded="CARS ON THE DECK",
           bays="BUILT FOR MULTI-DECK RIGS", reviews="WHAT DRIVERS SAY", fleet="CALL BEFORE IT BREAKS",
           warranty6="ON LABOR & WORKMANSHIP", cottrell="KEEP YOUR FACTORY WARRANTY")
for _k, _t in {"deckdown": "Thunder", "sameday": "Hollywood waves", "pricing": "Kama Sutra", "callfirst": "Fields of space",
               "loaded": "Another Day", "bays": "Symphony one", "reviews": "Hyde and seek", "fleet": "Thunder",
               "warranty6": "Hollywood waves", "cottrell": "Kama Sutra"}.items():
    TRACK[_k] = (f"{_t}.mp3", f"{DJ}  ·  {_t}"); NEXT.setdefault(_k, None)
