"""One-click Seal helper for the user's full-screen AnyDesk layout."""
import ctypes
from ctypes import wintypes
import os,sys,json,time,re,hashlib,zipfile,threading,queue,io,subprocess
import urllib.request,urllib.parse,base64
from pathlib import Path
import tkinter as tk
from tkinter import filedialog
import cv2
import numpy as np
from PIL import Image,ImageGrab
from vision_tracker import match_red_bag

try: ctypes.windll.shcore.SetProcessDpiAwareness(2)
except (AttributeError,OSError): pass
ROOT=Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'SealVision'
ROOT.mkdir(parents=True,exist_ok=True)
sys.path.append(str(ROOT/'ocr_deps'))
u=ctypes.windll.user32
u.GetForegroundWindow.restype=wintypes.HWND
u.GetWindowTextW.argtypes=[wintypes.HWND,wintypes.LPWSTR,ctypes.c_int]
u.GetWindowRect.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.RECT)]
u.SetCursorPos.argtypes=[ctypes.c_int,ctypes.c_int]
u.ShowWindow.argtypes=[wintypes.HWND,ctypes.c_int]
u.SetForegroundWindow.argtypes=[wintypes.HWND]
u.GetClientRect.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.RECT)]
u.ClientToScreen.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.POINT)]
u.GetWindowThreadProcessId.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.DWORD)]

def find_anydesk():
    found=[]
    callback=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
    def inspect(hwnd,param):
        title=ctypes.create_unicode_buffer(1024);u.GetWindowTextW(hwnd,title,1024)
        if 'anydesk' in title.value.lower() and u.IsWindowVisible(hwnd):
            rect=wintypes.RECT();u.GetWindowRect(hwnd,ctypes.byref(rect))
            found.append(((rect.right-rect.left)*(rect.bottom-rect.top),hwnd))
        return True
    u.EnumWindows(callback(inspect),0)
    return max(found)[1] if found else None

def foreground():
    h=u.GetForegroundWindow(); t=ctypes.create_unicode_buffer(1024)
    u.GetWindowTextW(h,t,1024);r=wintypes.RECT();u.GetWindowRect(h,ctypes.byref(r))
    return t.value,[r.left,r.top,r.right,r.bottom]

def parse_ap(text):
    m=re.search(r'(\d{1,6})\s*/\s*(\d{1,6})',text)
    if not m:return None
    current,total=map(int,m.groups())
    return (current,total) if 0<=current<=total and 0<total<1_000_000 else None

def recognize_ap(engine,rgb):
    gray=cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY)
    votes={}
    for threshold in (100,150,210):
        image=np.where(gray>threshold,0,255).astype(np.uint8)
        image=cv2.resize(image,None,fx=6,fy=6,interpolation=cv2.INTER_NEAREST)
        image=cv2.copyMakeBorder(image,12,12,12,12,cv2.BORDER_CONSTANT,value=255)
        result,_=engine(cv2.cvtColor(image,cv2.COLOR_GRAY2BGR),use_det=False,use_cls=False)
        for text,confidence,*_ in result or []:
            value=parse_ap(text)
            if value and confidence>=.88:votes[value]=votes.get(value,0)+1
    valid=[value for value,count in votes.items() if count>=2]
    return valid[0] if len(valid)==1 else None

VERSION='1.7.1'
def stage_update(blob,home=ROOT):
    if len(blob)>5_000_000:raise ValueError('ไฟล์อัปเดตใหญ่เกินกำหนด')
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        if len(z.infolist())!=3 or sum(i.file_size for i in z.infolist())>5_000_000:raise ValueError('ขนาดหรือรายการไฟล์ไม่ถูกต้อง')
        m=json.loads(z.read('version.json'))
        if m.get('product')!='SealVision' or m.get('launcher_min',999)>1:raise ValueError('รุ่นอัปเดตไม่รองรับโปรแกรมนี้')
        if set(m['sha256'])!={'seal_app.py','vision_tracker.py'}:raise ValueError('รายการไฟล์ไม่ถูกต้อง')
        data={n:z.read(n) for n in m['sha256']}
        for name,body in data.items():
            if hashlib.sha256(body).hexdigest()!=m['sha256'][name]:raise ValueError('ไฟล์เสียหาย')
            compile(body,name,'exec')
    pending=home/'pending_update';pending.mkdir(parents=True,exist_ok=True)
    # Manifest is the commit marker: an interrupted write cannot be installed.
    (pending/'version.json').unlink(missing_ok=True)
    for name,body in data.items():(pending/name).write_bytes(body)
    temp=pending/'version.tmp';temp.write_text(json.dumps(m),encoding='utf-8');temp.replace(pending/'version.json')
    return m

def version_tuple(value):
    return tuple(int(n) for n in value.lstrip('v').split('.'))

def fetch_https(url,limit):
    if urllib.parse.urlparse(url).scheme!='https':raise ValueError('ต้องใช้ HTTPS')
    req=urllib.request.Request(url,headers={'User-Agent':'SealVision/'+VERSION,'Accept':'application/vnd.github+json'})
    with urllib.request.urlopen(req,timeout=25) as response:
        if urllib.parse.urlparse(response.url).scheme!='https':raise ValueError('ลิงก์ดาวน์โหลดไม่ปลอดภัย')
        data=response.read(limit+1)
    if len(data)>limit:raise ValueError('ไฟล์ใหญ่เกินกำหนด')
    return data

RETRY_PANEL=base64.b64decode('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')
def detect_retry(rgb):
    # Match the complete supplied Session Closed dialog, including its labels
    # and all three buttons. Never click based on a red rectangle alone.
    gray=cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY)
    gray=cv2.resize(gray,None,fx=.5,fy=.5,interpolation=cv2.INTER_AREA)
    reference=cv2.imdecode(np.frombuffer(RETRY_PANEL,np.uint8),cv2.IMREAD_GRAYSCALE)
    best=None
    for scale in (.65,.75,.8,.9,1.,1.1,1.25,1.5):
        template=cv2.resize(reference,None,fx=scale*.5,fy=scale*.5,interpolation=cv2.INTER_AREA)
        th,tw=template.shape
        if th>gray.shape[0] or tw>gray.shape[1]:continue
        _,score,_,point=cv2.minMaxLoc(cv2.matchTemplate(gray,template,cv2.TM_CCOEFF_NORMED))
        if score>=.90 and (best is None or score>best[0]):
            # Retry centre relative to the complete 625 x 262 dialog.
            best=(score,round(point[0]*2+370*scale),round(point[1]*2+230*scale))
    return best

SETTINGS_TITLE=base64.b64decode('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')
def detect_settings_minimize(rgb):
    # Only the generic title strip is stored, never the security settings.
    # Require the AnyDesk / Global Settings title AND window controls to match.
    gray=cv2.resize(cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY),None,fx=.5,fy=.5,interpolation=cv2.INTER_AREA)
    reference=cv2.imdecode(np.frombuffer(SETTINGS_TITLE,np.uint8),0)
    best=None
    for scale in (.65,.75,.8,.9,1.,1.1,1.25,1.5):
        template=cv2.resize(reference,None,fx=scale*.5,fy=scale*.5,interpolation=cv2.INTER_AREA)
        th,tw=template.shape
        if th>gray.shape[0] or tw>gray.shape[1]:continue
        _,score,_,point=cv2.minMaxLoc(cv2.matchTemplate(gray,template,cv2.TM_CCOEFF_NORMED))
        if score<.90:continue
        x,y=point;patch=gray[y:y+th,x:x+tw]
        left=max(5,round(220*scale*.5));right=max(5,round(110*scale*.5))
        title=float(cv2.matchTemplate(patch[:,:left],template[:,:left],cv2.TM_CCOEFF_NORMED)[0,0])
        controls=float(cv2.matchTemplate(patch[:,-right:],template[:,-right:],cv2.TM_CCOEFF_NORMED)[0,0])
        if title>=.90 and controls>=.90 and (best is None or score>best[0]):
            best=(score,round(x*2+649*scale),round(y*2+14*scale))
    return best

class Reader:
    def __init__(self):
        self.request=None;self.result=None;self.error='กำลังเตรียมตัวอ่าน AP';self.ready=False
        self.event=threading.Event();self.closed=False
        threading.Thread(target=self.work,daemon=True).start()
    def work(self):
        try:
            # The stable EXE carries Pillow's core. OCR needs additional Pillow
            # modules from the installed update, using the same Pillow version.
            import PIL
            extra_pil=str(ROOT/'ocr_deps'/'PIL')
            if extra_pil not in PIL.__path__:PIL.__path__.append(extra_pil)
            from rapidocr_onnxruntime import RapidOCR
            engine=RapidOCR(intra_op_num_threads=1,inter_op_num_threads=1)
            self.ready=True;self.error=''
            while not self.closed:
                self.event.wait(.5);self.event.clear()
                request=self.request;self.request=None
                if request is None:continue
                seq,image=request
                try:self.result=(seq,time.monotonic(),recognize_ap(engine,image))
                except Exception as ex:self.error=str(ex);self.result=(seq,time.monotonic(),None)
        except Exception as ex:
            self.error='เปิดตัวอ่าน AP ไม่ได้: '+str(ex)
            import traceback
            (ROOT/'ocr_error.log').write_text(traceback.format_exc(),encoding='utf-8')
    def submit(self,seq,image):
        self.request=(seq,image.copy());self.event.set()

class App:
    def __init__(self):
        self.root=tk.Tk();self.root.title('Seal Vision • อัตโนมัติ');self.root.geometry('660x740')
        self.running=False;self.arming=False;self.bound=None;self.seq=0;self.last_submit=0
        self.update_queue=queue.Queue();self.update_busy=False;self.release=None
        self.reader=Reader();self.status=tk.StringVar(value='เปิด AnyDesk เต็มจอให้เห็นเกม แล้วกดเริ่ม')
        self.ap_status=tk.StringVar(value='AP: กำลังเตรียมตัวอ่านตัวเลข')
        self.round_status=tk.StringVar(value='ทดสอบครบ 0 / 3 รอบ')
        self.test=tk.BooleanVar(value=True);self.hotkeys={}
        try:address=json.loads((ROOT/'connection.json').read_text(encoding='utf-8'))['address']
        except Exception:address=''
        self.address=tk.StringVar(value=address)
        self.last_connect=0;self.monitor=False;self.retry_hits=0;self.retry_at=-100;self.retry_check=0;self.settings_hits=0;self.settings_at=-100
        self.bag=cv2.imread(str(ROOT/'bag.png'))
        if self.bag is not None:self.bag=cv2.cvtColor(self.bag,cv2.COLOR_BGR2RGB)
        self.reset()
        tk.Label(self.root,text='Seal Vision',font=('Segoe UI',24,'bold')).pack(pady=14)
        tk.Label(self.root,text='AnyDesk เต็มจอแบบภาพอ้างอิง • ไม่ต้องตั้งข้อ 1–6').pack()
        tk.Label(self.root,text='Tab หาเป้าหมาย → 1 / 2 ใช้สกิล → Space เก็บถุงแดง').pack(pady=7)
        tk.Label(self.root,text='อ่านตัวเลข AP • ต่ำกว่า 50% กด 3 • ใช้เลขแถวบน').pack()
        connection=tk.Frame(self.root);connection.pack(pady=8)
        tk.Label(connection,text='AnyDesk ID').pack(side='left')
        tk.Entry(connection,textvariable=self.address,width=18).pack(side='left',padx=8)
        tk.Button(connection,text='เชื่อม AnyDesk',command=self.connect_anydesk).pack(side='left')
        tk.Checkbutton(self.root,text='ทดสอบ 3 รอบแล้วหยุดอัตโนมัติ',variable=self.test).pack(pady=8)
        tk.Button(self.root,text='เริ่ม (F8)',font=('Segoe UI',15,'bold'),bg='#b8e1c3',command=self.start).pack(fill='x',padx=30,pady=5)
        tk.Button(self.root,text='หยุด (F9)',font=('Segoe UI',13),command=self.stop).pack(fill='x',padx=30)
        tk.Label(self.root,textvariable=self.ap_status,fg='#006e87').pack(pady=8)
        tk.Label(self.root,textvariable=self.round_status).pack()
        tk.Label(self.root,textvariable=self.status,wraplength=610,justify='center').pack(padx=20,pady=8)
        self.update_button=tk.Button(self.root,text='ตรวจหาอัปเดต',command=self.online_update)
        self.update_button.pack(fill='x',padx=30,pady=5)
        tk.Label(self.root,text='รุ่น '+VERSION).pack()
        tk.Button(self.root,text='อัปเดตจากไฟล์ ZIP (สำรอง)',command=self.install_update).pack()
        self.root.protocol('WM_DELETE_WINDOW',self.close);self.root.after(150,self.tick)
        if '--test3' in sys.argv:self.root.after(1500,self.auto_start)
    def connect_anydesk(self):
        address=re.sub(r'\s+','',self.address.get())
        if not re.fullmatch(r'[0-9]{6,12}',address):
            self.status.set('กรอก AnyDesk ID ของเครื่องเกมก่อน');return
        if time.monotonic()-self.last_connect<15:
            self.status.set('ส่งคำขอแล้ว กรุณารอเครื่องเกมยอมรับ');return
        paths=[Path(os.environ.get('ProgramFiles(x86)','C:/Program Files (x86)'))/'AnyDesk/AnyDesk.exe',
               Path(os.environ.get('ProgramFiles','C:/Program Files'))/'AnyDesk/AnyDesk.exe',
               Path.home()/'Downloads/AnyDesk.exe']
        executable=next((p for p in paths if p.is_file()),None)
        if executable is None:
            selected=filedialog.askopenfilename(title='เลือก AnyDesk.exe',filetypes=[('AnyDesk','AnyDesk.exe')])
            if not selected:return
            executable=Path(selected)
        try:
            # Official session CLI; no passwords or permission changes.
            subprocess.Popen([str(executable),address],cwd=str(executable.parent))
            (ROOT/'connection.json').write_text(json.dumps({'address':address}),encoding='utf-8')
            self.last_connect=time.monotonic();self.monitor=True
            self.status.set('ส่งคำขอเชื่อม AnyDesk แล้ว • เมื่อเห็นเกมให้กดเริ่ม (F8)')
        except Exception as ex:self.status.set('เชื่อมไม่ได้: '+str(ex))
    def auto_start(self):
        if not self.reader.ready:
            if self.reader.error.startswith('เปิดตัวอ่าน'):
                self.status.set(self.reader.error);return
            self.root.after(1000,self.auto_start);return
        self.start()
    def event(self,event,**data):
        with (ROOT/'run_events.jsonl').open('a',encoding='utf-8') as f:
            f.write(json.dumps({'time':time.time(),'event':event,**data},ensure_ascii=False)+'\n')
    def reset(self):
        self.last={};self.cycles=0;self.phase='seek';self.phase_at=time.monotonic()
        self.ap=None;self.last_ap_seq=-1;self.good_ap=0;self.low=0;self.bag_hits=0;self.bag_absent=0
        self.baseline=None;self.combat=False;self.loot_sent=False;self.bag_observed=False
        self.last_frame=None;self.last_change=time.monotonic();self.last_max=None
        self.round_status.set('ทดสอบครบ 0 / 3 รอบ') if hasattr(self,'round_status') else None
    def start(self):
        if self.running or self.arming:return
        if self.bag is None:self.status.set('ยังไม่พบภาพอ้างอิงถุงแดง');return
        if not self.reader.ready:self.status.set(self.reader.error or 'กำลังเตรียมตัวอ่าน AP กรุณารอสักครู่');return
        self.reset();self.arming=True;self.monitor=True
        hwnd=find_anydesk()
        if hwnd is None:self.arming=False;self.status.set('ยังไม่พบ AnyDesk กรุณาเปิดการเชื่อมต่อเกมก่อน');return
        self.status.set('กำลังเปิด AnyDesk และตรวจ AP • F9 หยุด')
        self.target_hwnd=hwnd
        self.root.iconify();u.ShowWindow(hwnd,3);u.SetForegroundWindow(hwnd)
        self.root.after(1500,self.bind)
    def bind(self):
        if not self.arming:return
        title,rect=foreground();self.arming=False
        if 'anydesk' not in title.lower():
            self.root.deiconify();self.status.set('ยังไม่เริ่ม: เปิด AnyDesk เต็มจอไว้ด้านหน้า แล้วกดเริ่มใหม่');return
        sw,sh=u.GetSystemMetrics(0),u.GetSystemMetrics(1)
        if rect[2]-rect[0]<sw*.92 or rect[3]-rect[1]<sh*.85:
            self.root.deiconify();self.status.set('ยังไม่เริ่ม: ขยาย AnyDesk ให้เต็มหน้าจอตามภาพอ้างอิง');return
        self.bound=(title,rect);self.running=True;self.event('start',test3=self.test.get(),window=rect)
        self.status.set('เริ่มแล้ว • รอยืนยัน AP จากภาพก่อนส่งปุ่ม')
    def stop(self):
        was=self.running or self.arming;self.running=False;self.arming=False;self.monitor=False
        self.status.set('หยุดแล้ว');self.root.deiconify()
        if was:self.event('stop',cycles=self.cycles)
    def allowed(self):
        if not self.running or self.bound is None:return False
        title,rect=foreground()
        # The caption changes when AnyDesk reconnects. Bind to the actual
        # window handle so a reconnect does not leave the bot permanently paused.
        return u.GetForegroundWindow()==getattr(self,'target_hwnd',None) and 'anydesk' in title.lower()
    def key(self,code,now):
        if not self.allowed():return False
        u.keybd_event(code,0,0,0);time.sleep(.07);u.keybd_event(code,0,2,0)
        self.event('key',key=chr(code) if code in (49,50,51) else 'Space' if code==32 else 'Tab',ap=self.ap)
        return True
    def ground(self,image,now):
        # Fixed reference layout; reject points whose small patch contains UI,
        # bright objects or strong texture, rather than click a random pixel.
        h,w=image.shape[:2]
        for fx,fy in ((.60,.67),(.56,.70),(.59,.53)):
            x,y=round(w*fx),round(h*fy);patch=image[y-8:y+8,x-8:x+8]
            hsv=cv2.cvtColor(patch,cv2.COLOR_RGB2HSV)
            grass=((hsv[:,:,0]>=15)&(hsv[:,:,0]<=55)&(hsv[:,:,1]>35)&(hsv[:,:,2]>40)&(hsv[:,:,2]<230)).mean()
            if grass>.85 and patch.std()<65 and self.allowed():
                u.SetCursorPos(x,y);u.mouse_event(2,0,0,0,0);u.mouse_event(4,0,0,0,0)
                self.event('walk',point=[x,y]);self.last['walk']=now;return True
        return False
    def retry_session(self):
        now=time.monotonic()
        title,_=foreground()
        if 'anydesk' not in title.lower():self.retry_hits=0;return False
        hwnd=u.GetForegroundWindow()
        if now-self.retry_check<.8:return getattr(self,'retry_visible',False)
        self.retry_check=now
        image=np.asarray(ImageGrab.grab())
        settings=detect_settings_minimize(image)
        if settings:
            self.settings_hits+=1;self.retry_visible=True
            self.good_ap=0;self.low=0;self.reader.result=None
            self.last_change=now;self.last_frame=None
            self.status.set('พบ Global Settings บังเกม • กำลังย่อหน้าต่าง')
            if self.settings_hits>=2 and now-self.settings_at>=5 and u.GetForegroundWindow()==hwnd:
                _,x,y=settings
                u.SetCursorPos(x,y);u.mouse_event(2,0,0,0,0);u.mouse_event(4,0,0,0,0)
                self.settings_at=now;self.settings_hits=0
                self.event('anydesk_settings_minimized')
            return True
        self.settings_hits=0
        found=detect_retry(image);self.retry_visible=bool(found)
        if not found:self.retry_hits=0;return False
        self.retry_hits+=1;self.good_ap=0;self.low=0;self.reader.result=None
        self.last_change=now;self.last_frame=None
        self.status.set('Session หมด • รอกด Retry อัตโนมัติ • F9 หยุด')
        if self.retry_hits>=2 and now-self.retry_at>=30 and u.GetForegroundWindow()==hwnd:
            _,x,y=found
            # Same foreground window and a freshly matched complete dialog.
            u.SetCursorPos(x,y);u.mouse_event(2,0,0,0,0);u.mouse_event(4,0,0,0,0)
            self.retry_at=now;self.retry_hits=0
            self.phase='seek';self.baseline=None;self.combat=False
            self.bag_observed=False;self.loot_sent=False;self.bag_hits=0;self.bag_absent=0
            self.last.pop('loot_start',None);self.last_max=None
            if self.running:self.target_hwnd=hwnd
            self.event('anydesk_retry')
            self.status.set('กด Retry แล้ว • รอเชื่อมต่อและยืนยันภาพเกม')
        return True
    def tick(self):
        try:
            kind,value=self.update_queue.get_nowait()
            self.update_busy=False;self.update_button.config(state='normal')
            if kind=='release':
                self.release=value;self.update_button.config(text='อัปเดตเลย • '+value['tag_name'])
                self.status.set('พบรุ่นใหม่ กดอัปเดตเลยเพื่อติดตั้ง')
            elif kind=='installed':
                launcher=os.environ.get('SEAL_VISION_LAUNCHER')
                if launcher:
                    subprocess.Popen([launcher]);self.close();return
                self.status.set('ติดตั้งพร้อมแล้ว ปิดและเปิดโปรแกรมเดิมอีกครั้ง')
            else:self.status.set(value)
        except queue.Empty:pass
        for vk,action in ((0x77,self.start),(0x78,self.stop)):
            value=u.GetAsyncKeyState(vk);held=bool(value&0x8000)
            if (value&1) or (held and not self.hotkeys.get(vk)):action()
            self.hotkeys[vk]=held
        retry_wait=False
        if self.monitor:
            try:retry_wait=self.retry_session()
            except Exception as ex:self.status.set('ตรวจ Retry ไม่ได้: '+str(ex))
        if self.running and not retry_wait:
            try:self.step()
            except Exception as ex:
                self.stop();self.status.set('หยุดเพราะตรวจภาพไม่ได้: '+str(ex));self.event('error',message=str(ex))
        elif not self.reader.ready:self.ap_status.set(self.reader.error)
        self.root.after(120,self.tick)
    def step(self):
        now=time.monotonic()
        if not self.allowed():self.status.set('พัก: AnyDesk ต้องอยู่ด้านหน้าและเต็มจอขนาดเดิม');return
        image=np.asarray(ImageGrab.grab());h,w=image.shape[:2]
        # Pixel fractions from the user's full-screen 1917 x 1078 reference.
        def crop(box):
            x1,y1,x2,y2=box
            return image[round(y1*h/1078):round(y2*h/1078),round(x1*w/1917):round(x2*w/1917)]
        if now-self.last_submit>.65:
            self.seq+=1;self.reader.submit(self.seq,crop((345,171,429,188)));self.last_submit=now
        result=self.reader.result
        if result is None or now-result[1]>2 or result[2] is None:
            self.good_ap=0;self.low=0;self.status.set('รออ่าน AP ให้ตรงกัน • ไม่ส่งปุ่มขณะอ่านไม่ได้');return
        if result[0]!=self.last_ap_seq:
            self.last_ap_seq=result[0];self.ap=result[2]
            current,total=self.ap
            if self.last_max is not None and total!=self.last_max:
                self.stop();self.status.set('AP สูงสุดเปลี่ยนกะทันหัน กรุณาตรวจภาพก่อนเริ่มใหม่');return
            self.last_max=total;self.good_ap+=1;self.low=self.low+1 if current*2<total else 0
            self.event('ap',current=current,total=total)
            if self.baseline is not None and current<self.baseline-10:self.combat=True
        if self.good_ap<2:return
        current,total=self.ap
        self.ap_status.set(f'AP {current} / {total} = {current/total:.1%}')
        field=crop((175,200,1520,840))
        small=cv2.resize(field,(96,64))
        if self.last_frame is None or np.abs(small.astype(float)-self.last_frame.astype(float)).mean()>.8:self.last_change=now
        self.last_frame=small
        if now-self.last_change>18:
            self.stop();self.status.set('หยุด: ภาพเกมนิ่งเกิน 18 วินาที กรุณาตรวจการเชื่อมต่อ');return
        bag=match_red_bag(crop((700,430,1230,825)),self.bag)
        self.bag_hits=min(3,self.bag_hits+1) if bag>=.82 else 0
        self.bag_absent=min(4,self.bag_absent+1) if bag<.76 else 0
        if self.bag_hits==1:self.event('bag_seen',score=bag)
        if self.low>=2 and now-self.last.get('mana',0)>3:
            if self.key(51,now):self.last['mana']=now
            return
        if self.bag_hits>=2:
            self.phase='loot';self.bag_observed=True
            if now-self.last.get('loot',0)>1:
                if self.key(32,now):self.last['loot']=now;self.loot_sent=True
            self.status.set(f'พบถุงแดง {bag:.2f} • กด Space เก็บของ')
            if now-self.last.setdefault('loot_start',now)>10:
                self.stop();self.status.set('หยุด: ยังเห็นถุงหลังเก็บ 10 วินาที ต้องตรวจระยะเก็บ');return
            return
        if self.phase=='loot':
            if self.bag_absent<3:return
            if self.combat and self.bag_observed and self.loot_sent:
                self.cycles+=1;self.event('cycle_complete',cycle=self.cycles,ap=self.ap)
                self.round_status.set(f'ทดสอบครบ {self.cycles} / 3 รอบ')
                if self.test.get() and self.cycles>=3:
                    self.stop();self.status.set('ผ่าน: ตรวจภาพครบ ค้นหา → สกิล → ถุง → เก็บ 3 รอบ');return
            self.phase='seek';self.phase_at=now;self.baseline=None;self.combat=False;self.bag_observed=False;self.loot_sent=False
            self.last.pop('loot_start',None)
        self.status.set(f'ทำงาน: {self.phase} • AP {current}/{total} • ถุง {bag:.2f} • F9 หยุด')
        if self.phase=='seek':
            if now-self.last.get('walk',now)>8:self.ground(image,now)
            if self.key(9,now):self.phase='one';self.phase_at=now
        elif self.phase=='one' and now-self.phase_at>.8:
            if self.key(49,now):self.phase='two';self.phase_at=now
        elif self.phase=='two' and now-self.phase_at>.8:
            self.baseline=current
            if self.key(50,now):self.phase='wait';self.phase_at=now
        elif self.phase=='wait' and now-self.phase_at>3:
            if not self.combat and now-self.last.get('walk',0)>5:self.ground(image,now)
            if now-self.phase_at>5:self.phase='seek';self.phase_at=now
    def online_update(self):
        if self.update_busy:return
        try:
            config=json.loads((ROOT/'updates.json').read_text(encoding='utf-8'))
            repo=config['repository']
            if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repo):raise ValueError()
        except Exception:
            self.status.set('ยังไม่ได้เชื่อมแหล่งอัปเดต GitHub • ต้องเผยแพร่รุ่นแรกก่อน');return
        release=self.release
        if release:self.stop()
        self.update_busy=True;self.update_button.config(state='disabled')
        self.status.set('กำลังดาวน์โหลดและตรวจไฟล์...' if release else 'กำลังตรวจหารุ่นใหม่...')
        def worker():
            try:
                if release:
                    assets=[a for a in release.get('assets',[]) if re.fullmatch(r'SealVision-update-[0-9.]+\.zip',a['name'])]
                    if len(assets)!=1:raise ValueError('ไม่พบไฟล์อัปเดตที่ตรงรุ่น')
                    asset=assets[0];blob=fetch_https(asset['browser_download_url'],5_000_000)
                    digest=asset.get('digest')
                    if not digest or digest!='sha256:'+hashlib.sha256(blob).hexdigest():raise ValueError('ตรวจความถูกต้องของไฟล์ไม่ผ่าน')
                    # Check version before staging executable code.
                    with zipfile.ZipFile(io.BytesIO(blob)) as z:manifest=json.loads(z.read('version.json'))
                    if version_tuple(manifest['version'])!=version_tuple(release['tag_name']):raise ValueError('เลขรุ่นในไฟล์ไม่ตรงกัน')
                    stage_update(blob);self.update_queue.put(('installed',None))
                else:
                    value=json.loads(fetch_https('https://api.github.com/repos/'+repo+'/releases/latest',1_000_000))
                    if version_tuple(value['tag_name'])>version_tuple(VERSION):self.update_queue.put(('release',value))
                    else:self.update_queue.put(('status','ใช้รุ่นล่าสุดแล้ว ('+VERSION+')'))
            except Exception as ex:self.update_queue.put(('error','อัปเดตไม่สำเร็จ: '+str(ex)))
        threading.Thread(target=worker,daemon=True).start()
    def install_update(self):
        self.stop();path=filedialog.askopenfilename(title='เลือกไฟล์อัปเดต',filetypes=[('SealVision update','*.zip')])
        if not path:return
        try:
            stage_update(Path(path).read_bytes())
            self.status.set('อัปเดตพร้อมแล้ว ปิดและเปิดโปรแกรมเดิมอีกครั้ง')
        except Exception as ex:self.status.set('อัปเดตไม่สำเร็จ: '+str(ex))
    def close(self):
        self.running=False;self.arming=False;self.reader.closed=True;self.reader.event.set();self.root.destroy()

from vision_tracker import SaleVision, SALE_CATEGORIES, label_similarity


class TextReader:
    """Independent OCR queue; never block the UI or F9 on model inference."""
    def __init__(self):
        self.request=None;self.result=None;self.ready=False;self.error='';self.closed=False
        self.trace={'phase':'loading'}
        self.event=threading.Event();threading.Thread(target=self.work,daemon=True).start()
    def work(self):
        try:
            from rapidocr_onnxruntime import RapidOCR
            engine=RapidOCR(intra_op_num_threads=1,inter_op_num_threads=1,det_limit_type='max',det_limit_side_len=1280)
            self.ready=True
            self.trace={'phase':'idle'}
            while not self.closed:
                self.event.wait(.2);self.event.clear()
                job=self.request;self.request=None
                if job is None:continue
                token,image=job
                started=time.monotonic();self.trace={'phase':'running','token':token,'shape':list(image.shape)}
                try:
                    lines,_=engine(cv2.cvtColor(image,cv2.COLOR_RGB2BGR))
                    self.result=(token,time.monotonic(),lines or [])
                except Exception as error:self.error=str(error);self.result=(token,time.monotonic(),[])
                self.trace={'phase':'idle','token':token,'elapsed':time.monotonic()-started,'lines':len(self.result[2]),'error':self.error}
        except Exception as error:self.error=str(error)
    def submit(self,token,image):
        self.request=(token,image.copy());self.event.set()


def moonlight_window():
    """Validate process identity as well as the visible window caption."""
    matches=[]
    callback=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
    def inspect(hwnd,param):
        if not u.IsWindowVisible(hwnd):return True
        pid=wintypes.DWORD();u.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
        kernel=ctypes.windll.kernel32
        kernel.OpenProcess.restype=wintypes.HANDLE
        kernel.QueryFullProcessImageNameW.argtypes=[wintypes.HANDLE,wintypes.DWORD,wintypes.LPWSTR,ctypes.POINTER(wintypes.DWORD)]
        kernel.CloseHandle.argtypes=[wintypes.HANDLE]
        handle=kernel.OpenProcess(0x1000,False,pid.value)
        if not handle:return True
        try:
            path=ctypes.create_unicode_buffer(32768);size=wintypes.DWORD(len(path))
            if kernel.QueryFullProcessImageNameW(handle,0,path,ctypes.byref(size)) and Path(path.value).name.lower()=='moonlight.exe':
                title=ctypes.create_unicode_buffer(1024);u.GetWindowTextW(hwnd,title,1024)
                rect=wintypes.RECT();u.GetClientRect(hwnd,ctypes.byref(rect))
                if rect.right>500 and rect.bottom>300:matches.append((rect.right*rect.bottom,hwnd,title.value))
        finally:kernel.CloseHandle(handle)
        return True
    u.EnumWindows(callback(inspect),0)
    return max(matches) if matches else None


class MoonlightApp(App):
    def __init__(self):
        super().__init__()
        # Retain update controls, event logging, combat mode and stable EXE.
        for widget in self.root.winfo_children():widget.destroy()
        self.root.title('Seal Vision '+VERSION+' • Moonlight');self.root.geometry('720x880')
        self.text_reader=TextReader();self.sale_vision=SaleVision(ROOT)
        self.mode=tk.StringVar(value='ต่อสู้ / เก็บของ');self.teach=tk.StringVar(value=SALE_CATEGORIES[0])
        self.sale=None;self.text_token=0;self.text_at=0;self.text_state=None;self.text_seen=-1
        self.view_roi=(0.,0.,1.,1.);self.ap_roi=(.085,.022,.17,.075)
        try:
            calibration=json.loads((ROOT/'moonlight_view.json').read_text(encoding='utf-8'))
            self.view_roi=tuple(calibration['view']);self.ap_roi=tuple(calibration['ap'])
            if not all(0<=v<=1 for v in self.view_roi+self.ap_roi):raise ValueError()
        except Exception:self.view_roi=(0.,0.,1.,1.);self.ap_roi=(.085,.022,.17,.075)
        tk.Label(self.root,text='Seal Vision • Moonlight',font=('Segoe UI',23,'bold')).pack(pady=10)
        tk.Label(self.root,text='เปิดสตรีมเกม • ตั้งคีย์บอร์ดทั้งสองเครื่องเป็น English • F9 หยุด').pack()
        tk.Button(self.root,text='เปิด / แสดง Moonlight',command=self.connect_anydesk).pack(pady=5)
        tk.Button(self.root,text='1. ลากกรอบเฉพาะภาพเกม (ตัดขอบดำ / แถบชื่อ / Taskbar)',command=lambda:self.select_region('view')).pack(fill='x',padx=25)
        tk.Button(self.root,text='2. ลากกรอบเฉพาะตัวเลข AP เช่น 830 / 1205',command=lambda:self.select_region('ap')).pack(fill='x',padx=25,pady=3)
        tk.Label(self.root,text='จำหมวดครั้งแรก: เปิด I → ชี้ไอเทมให้ tooltip ขึ้น → กด F6').pack(pady=5)
        tk.OptionMenu(self.root,self.teach,*SALE_CATEGORIES).pack()
        tk.Label(self.root,text='เลือกหมวดด้านบนก่อนกด F6 • จำจากข้อความชมพู ไม่ใช่ชื่อหรือรูปไอเทม').pack()
        self.learned=tk.StringVar();tk.Label(self.root,textvariable=self.learned,wraplength=670).pack();self.update_learned()
        tk.OptionMenu(self.root,self.mode,'ต่อสู้ / เก็บของ','กลับเมืองและขายของ').pack(pady=6)
        tk.Checkbutton(self.root,text='โหมดต่อสู้: ทดสอบ 3 รอบแล้วหยุด',variable=self.test).pack()
        tk.Button(self.root,text='เริ่มโหมดที่เลือก (F8)',command=self.start,bg='#b8e1c3',font=('Segoe UI',14,'bold')).pack(fill='x',padx=25,pady=5)
        tk.Button(self.root,text='ขายไอเทม • /elim แล้วขายจนจบ',command=self.start_sale,bg='#ffe0a6',font=('Segoe UI',14,'bold')).pack(fill='x',padx=25,pady=4)
        tk.Button(self.root,text='หยุดทันที (F9)',command=self.stop,font=('Segoe UI',13)).pack(fill='x',padx=25)
        tk.Label(self.root,text='ขาย: /elim → หา Street Merchant → แลกเปลี่ยน → ตรวจหมวด → คลิกขวา → O',wraplength=670).pack(pady=6)
        tk.Label(self.root,text='ขายแล้วหยุด ไม่เดินกลับจุดล่า • ไม่พบภาพที่ยืนยันได้จะหยุด • ไม่มีการกด X อัตโนมัติ',wraplength=670).pack()
        tk.Label(self.root,textvariable=self.status,wraplength=670,fg='#006e87').pack(pady=9)
        tk.Label(self.root,textvariable=self.ap_status).pack();tk.Label(self.root,textvariable=self.round_status).pack()
        self.update_button=tk.Button(self.root,text='ตรวจหาอัปเดต',command=self.online_update)
        self.update_button.pack(fill='x',padx=25,pady=8)
        tk.Button(self.root,text='อัปเดตจากไฟล์ ZIP',command=self.install_update).pack()
        tk.Label(self.root,text='รุ่น '+VERSION).pack()
        self.status.set('พร้อมตั้งกรอบภาพ Moonlight และจำข้อความหมวดด้วย F6')

    def update_learned(self):
        self.learned.set('จำแล้ว: '+(' / '.join(k for k in SALE_CATEGORIES if k in self.sale_vision.labels) or 'ยังไม่มี'))

    def start_sale(self):
        self.stop();self.mode.set('กลับเมืองและขายของ');self.start()

    def connect_anydesk(self):
        found=moonlight_window()
        if found:u.ShowWindow(found[1],9);u.SetForegroundWindow(found[1]);return
        path=Path(os.environ.get('ProgramFiles','C:/Program Files'))/'Moonlight Game Streaming/Moonlight.exe'
        if path.exists():subprocess.Popen([str(path)])
        else:self.status.set('ไม่พบ Moonlight กรุณาเปิดเองก่อน')

    def client_rect(self):
        rect=wintypes.RECT();point=wintypes.POINT(0,0)
        u.GetClientRect(self.target_hwnd,ctypes.byref(rect));u.ClientToScreen(self.target_hwnd,ctypes.byref(point))
        return point.x,point.y,rect.right,rect.bottom

    def capture(self):
        x,y,w,h=self.client_rect();a,b,c,d=self.view_roi
        self.game_rect=(x+round(a*w),y+round(b*h),round((c-a)*w),round((d-b)*h))
        x,y,w,h=self.game_rect
        if w<400 or h<250:raise ValueError('กรอบภาพเกมเล็กเกินไป กรุณาตั้งใหม่')
        return np.asarray(ImageGrab.grab(bbox=(x,y,x+w,y+h)))

    def select_region(self,kind):
        self.stop();found=moonlight_window()
        if not found:self.status.set('เปิด Moonlight และเชื่อมเกมก่อน');return
        self.target_hwnd=found[1];self.root.iconify();u.SetForegroundWindow(found[1])
        def overlay():
            x,y,w,h=self.client_rect()
            if kind=='ap':
                a,b,c,d=self.view_roi;x+=round(a*w);y+=round(b*h);w=round((c-a)*w);h=round((d-b)*h)
            top=tk.Toplevel(self.root);top.title('Seal Vision • เลือกกรอบ '+kind);top.attributes('-topmost',True);top.attributes('-alpha',.35)
            if kind=='view':top.attributes('-fullscreen',True)
            top.geometry(f'{w}x{h}{x:+d}{y:+d}');canvas=tk.Canvas(top,bg='black',highlightthickness=0);canvas.pack(fill='both',expand=True)
            canvas.create_text(w//2,35,text='ลากกรอบภาพเกม' if kind=='view' else 'ลากเฉพาะตัวเลข AP',fill='yellow',font=('Segoe UI',20))
            drag={}
            def down(e):drag['start']=(e.x,e.y);drag['rect']=canvas.create_rectangle(e.x,e.y,e.x,e.y,outline='red',width=4)
            def move(e):
                if 'rect' in drag:canvas.coords(drag['rect'],*drag['start'],e.x,e.y)
            def done(e):
                if 'start' not in drag:return
                sx,sy=drag['start'];a,c=sorted((sx,e.x));b,d=sorted((sy,e.y))
                if c-a<20 or d-b<8:return
                offset_x=canvas.winfo_rootx()-x;offset_y=canvas.winfo_rooty()-y
                value=(max(0,(a+offset_x)/w),max(0,(b+offset_y)/h),min(1,(c+offset_x)/w),min(1,(d+offset_y)/h))
                if kind=='view':self.view_roi=value
                else:self.ap_roi=value
                (ROOT/'moonlight_view.json').write_text(json.dumps({'view':self.view_roi,'ap':self.ap_roi}),encoding='utf-8')
                top.destroy();self.root.deiconify();self.status.set('บันทึกกรอบภาพแล้ว')
            canvas.bind('<ButtonPress-1>',down);canvas.bind('<B1-Motion>',move);canvas.bind('<ButtonRelease-1>',done)
            top.bind('<Escape>',lambda e:(top.destroy(),self.root.deiconify()))
        self.root.after(500,overlay)

    def start(self):
        if self.running or self.arming:return
        found=moonlight_window()
        if not found:self.status.set('ไม่พบ Moonlight ที่เปิดอยู่');return
        if self.mode.get()=='กลับเมืองและขายของ':
            if len(self.sale_vision.labels)!=len(SALE_CATEGORIES):self.status.set('จำหมวดทั้ง 5 ด้วย F6 ก่อนเริ่มขาย เพื่อไม่ตีความจากสีเพียงอย่างเดียว');return
            if not self.text_reader.ready:self.status.set('กำลังเตรียม OCR: '+self.text_reader.error);return
        elif not self.reader.ready or self.bag is None:self.status.set(self.reader.error or 'ยังไม่พร้อมอ่าน AP / ไม่พบ bag.png');return
        self.reset();self.target_hwnd=found[1];self.running=True;self.bound=found[2];self.monitor=False
        self.sale=None
        if self.mode.get()=='กลับเมืองและขายของ':
            self.sale={'state':'validate_game','since':time.monotonic(),'started':time.monotonic(),'walks':0,'slot':0,'sold':0,'skipped':0,'attempt':0}
        self.root.iconify();u.ShowWindow(self.target_hwnd,9);u.SetForegroundWindow(self.target_hwnd)
        self.status.set('เริ่มแล้ว • F9 หยุด')

    def allowed(self):
        if not self.running or u.GetForegroundWindow()!=getattr(self,'target_hwnd',None):return False
        x,y,w,h=self.client_rect()
        return w>400 and h>250 and not u.IsIconic(self.target_hwnd)

    def click_game(self,p,right=False,move=False):
        if not self.allowed():return False
        x,y,w,h=self.game_rect;px,py=map(round,p)
        if not (0<=px<w and 0<=py<h):return False
        # SDL's input path does not reliably forward SetCursorPos-only moves.
        # Inject a real absolute movement so hovering also reaches Sunshine.
        vx,vy=u.GetSystemMetrics(76),u.GetSystemMetrics(77)
        vw,vh=u.GetSystemMetrics(78),u.GetSystemMetrics(79)
        u.mouse_event(0xC001,round((x+px-vx)*65535/max(1,vw-1)),round((y+py-vy)*65535/max(1,vh-1)),0,0)
        if not move:
            down,up=(8,16) if right else (2,4)
            u.mouse_event(down,0,0,0,0);u.mouse_event(up,0,0,0,0)
        return True

    def key(self,code,now):
        if not self.allowed():return False
        scan=u.MapVirtualKeyW(code,0)
        u.keybd_event(code,scan,0,0);time.sleep(.07);u.keybd_event(code,scan,2,0)
        self.event('key',code=code,ap=self.ap)
        return True

    def transition(self,state):
        self.sale['state']=state;self.sale['since']=time.monotonic();self.sale['hits']=0
        self.text_reader.result=None;self.text_state=None
        self.event('sale_state',state=state)

    def fail_sale(self,reason):
        sold=self.sale['sold'];self.stop();self.sale=None
        self.status.set(f'หยุดขาย: {reason} • ขายแล้ว {sold} ชิ้น')

    def ocr(self,image,state):
        now=time.monotonic();result=self.text_reader.result
        lines=None
        if result and result[0]==self.text_token and self.text_state==state and self.text_seen!=result[0]:
            lines=result[2];self.text_seen=result[0]
        if (result is not None or self.text_state!=state) and now-self.text_at>.8:
            self.text_token+=1;self.text_at=now;self.text_state=state;self.text_reader.result=None
            self.text_reader.submit(self.text_token,image)
        return lines

    def teach_label(self):
        if self.running:self.status.set('หยุด F9 ก่อนจำหมวด');return
        found=moonlight_window()
        if not found or u.GetForegroundWindow()!=found[1]:self.status.set('ชี้ไอเทมใน Moonlight ให้ tooltip ขึ้น แล้วกด F6');return
        self.target_hwnd=found[1];image=self.capture();point=wintypes.POINT();u.GetCursorPos(ctypes.byref(point))
        slot=(point.x-self.game_rect[0],point.y-self.game_rect[1]);grid=self.sale_vision.grid(image)
        if not grid or min(np.hypot(slot[0]-p[0],slot[1]-p[1]) for p in grid)>25:self.status.set('ชี้ช่องไอเทมในกระเป๋าก่อนกด F6');return
        try:self.sale_vision.learn(self.teach.get(),self.sale_vision.tooltip(image,slot));self.update_learned();self.status.set('จำหมวด '+self.teach.get()+' แล้ว')
        except Exception as error:self.status.set(str(error))

    def tick(self):
        # App.tick supplies update handling and F8/F9; add F6 edge detection.
        if hasattr(self,'sale_vision'):
            value=u.GetAsyncKeyState(0x75);held=bool(value&0x8000)
            if (value&1) or (held and not self.hotkeys.get(0x75)):self.teach_label()
            self.hotkeys[0x75]=held
        super().tick()

    def step(self):
        if not self.allowed():
            if self.sale:self.fail_sale('Moonlight ไม่อยู่ด้านหน้า กดเริ่มใหม่เมื่อพร้อม')
            else:self.status.set('พัก: เปิดภาพเกม Moonlight ด้านหน้า')
            return
        image=self.capture()
        if self.sale:
            previous=self.sale.setdefault('image_shape',image.shape)
            if previous!=image.shape:self.fail_sale('ขนาดภาพเปลี่ยน เริ่มใหม่หลังตั้งกรอบ');return
        if self.sale:self.sale_step(image);return
        # Preserve combat state machine, using game-relative capture and an AP
        # crop learned for this stream rather than AnyDesk's old screen layout.
        self.combat_step(image)

    def sale_step(self,image):
        s=self.sale;now=time.monotonic();state=s['state'];elapsed=now-s['since'];h,w=image.shape[:2]
        self.status.set(f'ขาย: {state} • ขายแล้ว {s["sold"]} • ข้าม {s["skipped"]} • F9 หยุด')
        if now-s['started']>600:self.fail_sale('ครบเวลาค้นหา/ขาย 10 นาที');return
        if elapsed>40:self.fail_sale('รอภาพยืนยันขั้นตอน '+state+' เกินเวลา');return
        if state=='validate_game':
            if self.sale_vision.find(image,'hud_ap',.83):self.transition('chat')
            elif elapsed>4:self.fail_sale('ไม่พบ HUD ของ Seal ตรวจกรอบภาพเกมและเปิดสตรีม')
            return
        if state=='chat':
            self.click_game((w*.13,h*.994))
            if s['attempt']:
                self.key(13,now)
            self.transition('type');return
        if state=='type' and elapsed>.5:
            for code in (0xBF,ord('E'),ord('L'),ord('I'),ord('M')):
                if not self.key(code,now):self.fail_sale('หน้าต่างเปลี่ยนขณะพิมพ์');return
            self.transition('verify_command');return
        if state=='verify_command':
            lines=self.ocr(image[int(h*.96):,:int(w*.35)],state)
            if self.text_reader.error:self.fail_sale('OCR: '+self.text_reader.error);return
            if lines is None:return
            text=' '.join(str(v[1]).lower().replace(' ','') for v in lines if v[2]>=.75)
            if '/elim' in text:
                self.key(13,now);self.transition('warp');return
            if elapsed>5:
                # A retry only focuses an empty chat; never submit unverified text.
                if s['attempt']>=1:self.fail_sale('พิมพ์ /elim ไม่ขึ้น ตรวจภาษา English และช่องแชท');return
                s['attempt']+=1;self.transition('chat')
            return
        if state=='warp' and elapsed>5:
            self.transition('merchant');return
        if state=='merchant':
            lines=self.ocr(image,state)
            if lines is None:return
            matches=[line for line in lines if line[2]>=.83 and 'streetmerchant' in re.sub('[^a-z]','',line[1].lower())]
            if len(matches)==1:
                s['hits']=s.get('hits',0)+1
                if s['hits']<2:return
                box=np.array(matches[0][0]);center=box.mean(axis=0);s['merchant_name']=center.tolist()
                # Nameplate text must also be green, as in the supplied NPC.
                x1,y1=box.min(axis=0).astype(int);x2,y2=box.max(axis=0).astype(int)
                crop=image[max(0,y1):y2+1,max(0,x1):x2+1]
                if not crop.size or ((crop[:,:,1]>crop[:,:,0]*1.15)&(crop[:,:,1]>crop[:,:,2]*1.1)).mean()<.025:return
                self.click_game((center[0],center[1]+36*h/1050));self.transition('trade');return
            if elapsed>3 and s['walks']<60:
                # Bounded search in the user-specified upper-left direction.
                # Search is bounded by 60 moves and the overall deadline.
                if s['walks'] and s['walks']%3==0 and s.get('rotated_at')!=s['walks']:
                    self.click_game((w*.53,h*.58),move=True)
                    if not self.allowed():return
                    u.mouse_event(8,0,0,0,0)
                    try:u.mouse_event(1,95,0,0,0)
                    finally:u.mouse_event(16,0,0,0,0)
                    s['rotated_at']=s['walks'];self.transition('rotate_wait');return
                point=(w*(.39 if s['walks']%2==0 else .44),h*.39)
                if self.sale_vision.find(image,'shop') or self.sale_vision.grid(image):
                    if self.sale_vision.grid(image):self.key(ord('I'),now);self.transition('merchant');return
                patch=image[int(point[1])-10:int(point[1])+10,int(point[0])-10:int(point[0])+10]
                hsv=cv2.cvtColor(patch,cv2.COLOR_RGB2HSV)
                if ((hsv[:,:,0]>10)&(hsv[:,:,0]<40)&(hsv[:,:,1]<170)&(hsv[:,:,2]>80)).mean()<.75:self.fail_sale('พื้นทางค้นหาแม่ค้าไม่ชัดเจน');return
                self.click_game(point);s['walks']+=1;self.transition('walk_wait');return
            if elapsed>8 and s['walks']>=60:self.fail_sale('ไม่พบชื่อ Street Merchant หลังค้นหาครบกำหนด')
            return
        if state=='rotate_wait' and elapsed>1.5:self.transition('merchant');return
        if state=='walk_wait' and elapsed>2.5:self.transition('merchant');return
        if state=='trade':
            if self.sale_vision.find(image,'shop') and self.sale_vision.grid(image):self.transition('scan');return
            anchor=self.sale_vision.find(image,'trade',.88)
            if anchor:
                s['hits']=s.get('hits',0)+1
                if s['hits']>=2:self.click_game((anchor['x']+anchor['w']/2,anchor['y']+anchor['h']/2));self.transition('shop')
            elif elapsed>4:self.transition('merchant')
            return
        if state=='shop':
            if self.sale_vision.find(image,'shop') and self.sale_vision.grid(image):self.transition('scan')
            elif self.sale_vision.find(image,'shop') and elapsed>1:
                self.key(ord('I'),now);self.transition('inventory_wait')
            return
        if state=='inventory_wait':
            if self.sale_vision.find(image,'shop') and self.sale_vision.grid(image):self.transition('scan')
            return
        if state=='scan':
            if not self.sale_vision.find(image,'shop'):self.fail_sale('หน้าร้านหายไป');return
            grid=self.sale_vision.grid(image)
            if not grid:self.fail_sale('ไม่พบช่องกระเป๋า');return
            if s['slot']>=len(grid):self.fail_sale('ตรวจครบช่องกระเป๋าแล้ว');return
            s['point']=grid[s['slot']]
            px,py=s['point'];icon=image[max(0,py-10):py+10,max(0,px-10):px+10]
            if icon.size and icon.reshape(-1,3).std(axis=0).max()<7:
                s['slot']+=1;self.transition('scan');return
            self.click_game(s['point'],move=True);self.transition('tooltip');return
        if state=='tooltip' and elapsed>.25:
            label=self.sale_vision.tooltip(image,s['point']);category=self.sale_vision.category(label)
            if category:
                s['category']=category;s['label']=label;self.transition('verify_item')
            elif elapsed>1.5:s['slot']+=1;s['skipped']+=1;self.transition('scan')
            return
        if state=='verify_item' and elapsed>.12:
            label=self.sale_vision.tooltip(image,s['point'])
            if self.sale_vision.category(label)!=s['category'] or label_similarity(label,s['label'])<.90:
                self.fail_sale('หมวดไอเทมเปลี่ยนก่อนคลิกขวา');return
            if not self.sale_vision.find(image,'shop'):self.fail_sale('ไม่พบหน้าร้าน');return
            px,py=s['point'];s['icon_before']=image[py-10:py+10,px-10:px+10].copy()
            self.click_game(s['point'],right=True);self.transition('confirm');return
        if state=='confirm':
            anchor=self.sale_vision.find(image,'confirm',.90)
            if not anchor:return
            # Require the whole supplied sale-dialog style as well as a separate
            # pair of O/X buttons. Item name is intentionally not matched.
            ax,ay=anchor['x'],anchor['y'];scale=anchor['scale']
            crop=image[max(0,round(ay-92*scale)):ay, max(0,round(ax-75*scale)):min(w,round(ax+190*scale))]
            if crop.size==0:return
            # White text on a dark translucent panel must be present above O/X.
            white=(crop.min(axis=2)>155);dark=(crop.max(axis=2)<145)
            if white.mean()<.012 or dark.mean()<.18:return
            # Thai sale phrase is matched directly; no OCR/model wait here.
            dialog=self.sale_vision.find(image,'sale_text',.88)
            if not dialog:return
            if abs(dialog['x']-(ax-45*scale))>18*scale or abs(dialog['y']-(ay-72*scale))>18*scale:return
            s['hits']=s.get('hits',0)+1
            if s['hits']<2:return
            s['confirm_anchor']=anchor
            self.click_game((ax+14*scale,ay+20*scale));self.transition('sold');return
        if state=='sold':
            if self.sale_vision.find(image,'confirm',.88):return
            if not self.sale_vision.find(image,'shop'):self.fail_sale('ร้านปิดหลังยืนยันขาย');return
            if elapsed>.25:
                px,py=s['point'];icon=image[py-10:py+10,px-10:px+10]
                if icon.shape!=s['icon_before'].shape:self.fail_sale('ขนาดภาพเปลี่ยนหลังขาย');return
                if np.abs(icon.astype(float)-s['icon_before'].astype(float)).mean()<8:
                    if elapsed>3:self.fail_sale('ไอเทมยังไม่เปลี่ยนหลังยืนยันขาย')
                    return
                s['sold']+=1;self.event('sold_category',category=s['category']);self.transition('scan')

    def combat_step(self,image):
        now=time.monotonic();h,w=image.shape[:2]
        a,b,c,d=self.ap_roi
        if now-self.last_submit>.65:
            self.seq+=1;self.reader.submit(self.seq,image[round(b*h):round(d*h),round(a*w):round(c*w)]);self.last_submit=now
        result=self.reader.result
        if result is None or now-result[1]>2 or result[2] is None:
            self.good_ap=0;self.status.set('รอ AP • ตรวจกรอบ AP ที่ตั้งไว้');return
        if result[0]!=self.last_ap_seq:
            self.last_ap_seq=result[0];self.ap=result[2];current,total=self.ap
            if self.last_max is not None and total!=self.last_max:self.stop();self.status.set('AP สูงสุดเปลี่ยน หยุดตรวจภาพ');return
            self.last_max=total;self.good_ap+=1;self.low=self.low+1 if current*2<total else 0
            if self.baseline is not None and current<self.baseline-10:self.combat=True
        if self.good_ap<2:return
        current,total=self.ap;self.ap_status.set(f'AP {current}/{total}')
        small=cv2.resize(image,(96,64))
        if self.last_frame is None or np.abs(small.astype(float)-self.last_frame.astype(float)).mean()>.8:self.last_change=now
        self.last_frame=small
        if now-self.last_change>18:self.stop();self.status.set('ภาพเกมนิ่งเกิน 18 วินาที');return
        bag=match_red_bag(image[int(h*.3):int(h*.82),int(w*.3):int(w*.7)],self.bag)
        self.bag_hits=min(3,self.bag_hits+1) if bag>=.82 else 0
        self.bag_absent=min(4,self.bag_absent+1) if bag<.76 else 0
        if self.low>=2 and now-self.last.get('mana',0)>3:
            if self.key(51,now):self.last['mana']=now
            return
        if self.bag_hits>=2:
            self.phase='loot';self.bag_observed=True
            if now-self.last.get('loot',0)>1:
                if self.key(32,now):self.last['loot']=now;self.loot_sent=True
            if now-self.last.setdefault('loot_start',now)>10:self.stop();self.status.set('เก็บถุงไม่สำเร็จ หยุดตรวจภาพ')
            return
        if self.phase=='loot':
            if self.bag_absent<3:return
            if self.combat and self.bag_observed and self.loot_sent:
                self.cycles+=1;self.round_status.set(f'ทดสอบครบ {self.cycles}/3 รอบ')
                if self.test.get() and self.cycles>=3:self.stop();self.status.set('จบการทดสอบ 3 รอบ');return
            self.phase='seek';self.phase_at=now;self.baseline=None;self.combat=False;self.bag_observed=False;self.loot_sent=False;self.last.pop('loot_start',None)
        if self.phase=='seek':
            if self.key(9,now):self.phase='one';self.phase_at=now
        elif self.phase=='one' and now-self.phase_at>.8:
            if self.key(49,now):self.phase='two';self.phase_at=now
        elif self.phase=='two' and now-self.phase_at>.8:
            self.baseline=current
            if self.key(50,now):self.phase='wait';self.phase_at=now
        elif self.phase=='wait' and now-self.phase_at>5:self.phase='seek';self.phase_at=now

    def close(self):
        if hasattr(self,'text_reader'):self.text_reader.closed=True;self.text_reader.event.set()
        super().close()


if __name__=='__main__':
    app=MoonlightApp()
    if os.environ.get('SEAL_VISION_DIAGNOSTIC')=='1':
        app.root.withdraw()
        def sample_ocr():
            sample=np.zeros((100,700,3),np.uint8)
            cv2.putText(sample,'/elim',(20,65),cv2.FONT_HERSHEY_SIMPLEX,1.5,(255,255,255),2)
            app.text_reader.submit(-1,sample)
        app.root.after(4000,sample_ocr)
        def diagnostic():
            report={'version':VERSION,'ap_reader_ready':app.reader.ready,'ap_reader_error':app.reader.error,
                    'text_reader_ready':app.text_reader.ready,'text_reader_error':app.text_reader.error,'ocr_trace':app.text_reader.trace,
                    'ocr_result':app.text_reader.result,
                    'controls':[w.cget('text') for w in app.root.winfo_children() if isinstance(w,tk.Button)]}
            (ROOT/'diagnostic.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
            app.close()
        app.root.after(15000,diagnostic)
    app.root.mainloop()
