"""Track a player's cyan name, then read the blue bar at its relative offset."""
import cv2
import numpy as np


def name_mask(rgb):
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    return cv2.inRange(hsv, np.array([65, 65, 65]), np.array([103, 255, 255]))


def mana_mask(rgb):
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    return cv2.inRange(hsv, np.array([75, 35, 60]), np.array([135, 255, 255]))


def monster_bar(rgb, player):
    """Visible red HP line with cyan name, excluding the tracked player's HUD."""
    hsv=cv2.cvtColor(rgb,cv2.COLOR_RGB2HSV)
    red=cv2.inRange(hsv,np.array([0,90,80]),np.array([12,255,255])) | cv2.inRange(hsv,np.array([165,90,80]),np.array([179,255,255]))
    _,_,stats,_=cv2.connectedComponentsWithStats(red)
    cyan=name_mask(rgb)
    px,py,pw,ph=player['bar']
    for x,y,w,h,area in stats[1:]:
        if not (12<=w<=160 and 1<=h<=6 and w>=4*h):
            continue
        if abs((x+w/2)-(px+pw/2))<max(90,pw*2) and abs(y-py)<50:
            continue
        text=cyan[max(0,y-22):y,max(0,x-45):min(rgb.shape[1],x+w+45)]
        if (text>0).sum()>=15:
            return 1.
    return 0.


def match_red_bag(rgb, template):
    """Shape+color matching over multiple scales; red flowers alone are insufficient."""
    if template is None:
        return 0.
    best=0.
    hsv=cv2.cvtColor(rgb,cv2.COLOR_RGB2HSV)
    red=((((hsv[:,:,0]<=12)|(hsv[:,:,0]>=165)) & (hsv[:,:,1]>85) & (hsv[:,:,2]>70)).astype(np.uint8))*255
    # Do not close the live mask: glow effects can otherwise connect a small
    # bag to a large orange patch of ground.
    contours,_=cv2.findContours(red,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    refh=cv2.cvtColor(template,cv2.COLOR_RGB2HSV)
    ref=((((refh[:,:,0]<=12)|(refh[:,:,0]>=165)) & (refh[:,:,1]>85) & (refh[:,:,2]>70)).astype(np.uint8))*255
    ref=cv2.morphologyEx(ref,cv2.MORPH_CLOSE,np.ones((3,3),np.uint8))
    refs,_=cv2.findContours(ref,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    reference=max(refs,key=cv2.contourArea) if refs else None
    for contour in contours:
        x,y,w,h=cv2.boundingRect(contour)
        if not (7<=w<=65 and 10<=h<=85 and 1.2<=h/w<=2.5):continue
        if not (.32<=cv2.contourArea(contour)/(w*h)<=.95):continue
        profile=(red[y:y+h,x:x+w]>0).sum(axis=1)
        if np.median(profile[:max(2,int(h*.30))]) < w*.45:continue
        patch=hsv[y:y+h,x:x+w]
        bow=((patch[:,:,1]<110)&(patch[:,:,2]>130))
        # A pale tie across the upper half distinguishes bags from flowers,
        # red target arrows, and red HP lines.
        band=bow[max(1,int(h*.18)):max(2,int(h*.60)),:]
        if not band.size or band.sum()<max(2,w*.12):continue
        if reference is None:continue
        distance=cv2.matchShapes(contour,reference,cv2.CONTOURS_MATCH_I1,0)
        if distance<.55:best=max(best,.95-min(.08,distance*.10))
    for scale in (.65,.75,.85,1.,1.15,1.3):
        w=max(5,round(template.shape[1]*scale)); h=max(5,round(template.shape[0]*scale))
        if h>rgb.shape[0] or w>rgb.shape[1]:
            continue
        t=cv2.resize(template,(w,h))
        scores=cv2.matchTemplate(rgb,t,cv2.TM_CCOEFF_NORMED)
        _,score,_,point=cv2.minMaxLoc(scores)
        x,y=point
        patch=rgb[y:y+h,x:x+w]
        hsv=cv2.cvtColor(patch,cv2.COLOR_RGB2HSV)
        red=(((hsv[:,:,0]<=12)|(hsv[:,:,0]>=165)) & (hsv[:,:,1]>85) & (hsv[:,:,2]>65)).mean()
        if red>=.18:
            best=max(best,float(score))
    return best


def learn_player(rgb):
    """Select the player name AND all three complete bars while mana is full."""
    mask = mana_mask(rgb)
    _, _, stats, _ = cv2.connectedComponentsWithStats(mask)
    bars = [s for s in stats[1:] if s[2] >= 16 and 1 <= s[3] <= 8 and s[2] / s[3] >= 5]
    if not bars:
        raise ValueError('ไม่พบแถบสีฟ้าแนวนอน เลือกชื่อของคุณพร้อมแถบแดง ฟ้า และดำด้านล่าง')
    x, y, w, h, _ = max(bars, key=lambda s: s[2])
    x, y, w, h = map(int, (x, y, w, h))
    if y < 8 or y + h + 2 >= rgb.shape[0] or x < 1 or x + w >= rgb.shape[1]:
        raise ValueError('กรอบแคบเกินไป ต้องเห็นชื่อและขอบของทั้งสามแถบครบ')
    # Bottom dark strip is the fixed-width reference. This prevents treating a
    # partly filled blue segment as a full bar during calibration.
    dark = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY) < 90
    candidates = []
    for row in range(y+h+1, min(y+h+10, rgb.shape[0])):
        padded = np.pad(dark[row].astype(np.int8), (1, 1))
        edges = np.diff(padded)
        for left, right in zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)):
            width = int(right-left)
            if abs(left-x) <= 4 and .85*w <= width <= 1.25*w:
                candidates.append((abs(width-w)+abs(left-x), int(left), row, width))
    if not candidates:
        # A partly filled lower bar has no full-width black run. Use the
        # aligned HP strip above mana as the width reference instead.
        hsv=cv2.cvtColor(rgb,cv2.COLOR_RGB2HSV)
        red=(((hsv[:,:,0]<20)|(hsv[:,:,0]>150)) & (hsv[:,:,1]>45) & (hsv[:,:,2]>65)).astype(np.uint8)*255
        _,_,redstats,_=cv2.connectedComponentsWithStats(red)
        hp=[s for s in redstats[1:] if abs(int(s[0])-x)<=4 and
            y-12<=int(s[1])<y and 1<=s[3]<=6 and .85*w<=s[2]<=1.3*w]
        if not hp:
            raise ValueError('ไม่พบขอบแถบล่างหรือแถบ HP ที่จัดแนวกัน กรุณาเลือกสามแถบให้ครบ')
        ref=max(hp,key=lambda s:s[2]); bx,bw=int(ref[0]),int(ref[2])
        rows=range(y+h+1,min(y+h+10,rgb.shape[0]))
        bottom_y=max(rows,key=lambda row:dark[row,bx:bx+bw].mean())
        if dark[bottom_y,bx:bx+bw].mean()<.3:
            raise ValueError('ภาพขอบแถบไม่ชัด กรุณาเก็บภาพใหม่')
    else:
        _, bx, bottom_y, bw = min(candidates)
    if w / bw < .90:
        raise ValueError('มานายังไม่เต็ม หรือกรอบแถบไม่ชัด กรุณาตั้งภาพตอนมานาเต็ม')
    top = max(0, y-35)
    names = name_mask(rgb[top:max(top+1, y-3)])
    # Cyan letters, unlike the bar, are not continuous horizontal stripes.
    names[(names > 0).mean(axis=1) > .70] = 0
    active = np.flatnonzero((names > 0).sum(axis=1) >= max(4, w*.08))
    if active.size:
        groups = np.split(active, np.flatnonzero(np.diff(active)>2)+1)
        groups = [g for g in groups if len(g)>=3]
        if groups:
            line = groups[-1]
            names[:max(0, int(line[0])-1)] = 0
            names[int(line[-1])+2:] = 0
    ys, xs = np.nonzero(names)
    if len(xs) < 18:
        raise ValueError('ยังไม่เห็นชื่อสีฟ้าของคุณชัดเจน ให้ลากกรอบสูงขึ้นจนเห็นชื่อครบ')
    nx, ny, nr, nb = int(xs.min()), top+int(ys.min()), int(xs.max()+1), top+int(ys.max()+1)
    template = name_mask(rgb[ny:nb, nx:nr])
    return template, {'bar': [bx-nx, y-ny, bw, h], 'bottom': bottom_y-ny,
                      'name_shape': list(template.shape), 'version': 1}


def track_player(rgb, template, descriptor, previous=None):
    """Unknown returns None (never zero mana). Search the whole selected field."""
    th, tw = template.shape
    if rgb.shape[0] < th or rgb.shape[1] < tw:
        return None
    field = name_mask(rgb)
    result = cv2.matchTemplate(field, template, cv2.TM_CCORR_NORMED)
    result = np.nan_to_num(result, nan=0., posinf=0., neginf=0.)
    # Inspect several distinct candidates, but require both name and bar geometry.
    candidates = []
    for _ in range(5):
        _, score, _, p = cv2.minMaxLoc(result)
        if score < .80:
            break
        x, y = p
        bx, by, bw, bh = descriptor['bar']
        x1, y1 = x+bx, y+by
        bottom = y+descriptor['bottom']
        if x1 >= 0 and y1 >= 0 and x1+bw <= rgb.shape[1] and bottom < rgb.shape[0]:
            gray = cv2.cvtColor(rgb[max(0,bottom-1):bottom+2, x1:x1+bw], cv2.COLOR_RGB2GRAY)
            dark_support = (gray < 100).mean(axis=1).max() if gray.size else 0
            if dark_support >= .55 and y1+bh <= rgb.shape[0]:
                blue = mana_mask(rgb[y1:y1+bh, x1:x1+bw])
                cols = (blue > 0).mean(axis=0) >= .30
                # Count filled columns; tolerate tiny gaps from compression.
                fraction = float(cols.mean())
                distance = np.hypot(x-previous[0], y-previous[1]) if previous else 0
                candidates.append((score - min(.05, distance/10000), float(score),
                                   fraction, (x,y), (x1,y1,bw,bh)))
        result[max(0,y-th//2):y+th, max(0,x-tw//2):x+tw] = 0
    if not candidates:
        return None
    candidates.sort(reverse=True)
    if len(candidates)>1 and candidates[0][0]-candidates[1][0] < .035:
        return None  # Two similar names: no confident player identity.
    _, score, fraction, position, bar = candidates[0]
    return {'mana': fraction, 'confidence': score, 'position': position, 'bar': bar}
