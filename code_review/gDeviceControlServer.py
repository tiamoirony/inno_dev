#!/usr/bin/env python3
"""
Very simple HTTP server in python for logging requests
Usage::
    ./server.py [<port>]
"""
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse
import logging
import subprocess
import json
import os
import threading
import requests
from gControlGpio import gpioCtrl
from gPlaySound import gPlaySound
from gDetectCamera import gDetectPlateRecognition
from gTimer import timer
from gSystemInfo import getLprSysInfo
import gProcesses
import config
import log

chargerEvent = threading.Event()
#status = oldstatus = '0,0'
oldChargerStatus = '0'
statusList=[]

def ctrlLed(color, onoff) :
    ret=200
    if onoff=='on':
        onoff=1
    elif onoff=='off':
        onoff=0
    else :
        ret=404
    if color=='blue':
        gpioCtrl.greenSuccessLed(onoff)
    elif color=='red':
        gpioCtrl.redWarningBlinkLed(onoff)
    else :
        ret=404
        
    return ret
        
        
def ctrlTimer(cmd) :
    logging.info(str(cmd))
    ret=200
    if cmd[3]=='start' :
        if cmd[4]=='allow' :
            timer.selectTimer('limit')
            timer.startTimer()
        elif cmd[4]=='notallow' :
            timer.selectTimer('notallow')
            timer.startTimer()
        else :
            ret=404
    elif cmd[3]=='kill' :
        timer.clearTimer()
    else :
        ret = 404
def ctrlSound(cmd) :
    logging.info(str(cmd))
    ret = 200
    if cmd[3]=='volume' :
        gPlaySound.setVolume( int(cmd[4]) )
    elif cmd[3]=='warning' :
        gPlaySound.warningSoundPlay('unallow')
    else :
        ret = 404
def getDeviceStatus( cmd ) :
    logging.info( cmd )
    sysinfo = getLprSysInfo()
#    process = subprocess.check_output(['ps -ef | grep src/source/gLprSystem/__main__.py'])
    process = '1'
    retDict = {
        "status" : "1", # false or true
        "result" : {
             "device_id": sysinfo['device_id'],
             "process"  : process,
             "uptime"   : sysinfo['uptime'],
             "ip_addr"  : sysinfo['ipaddr'],
             "issue"    : "",
           },
        "error" : "" # if status false
    }
    
    return retDict
def reboot():
    os.system('reboot')
def setDeviceControl( cmd ) :
    logging.info( cmd )
    err = 200
#    response={'status':'1'}
    response={
        'status' : '1',
        'result' : { 'control':'',
                    'value':'-'
                    },
        'error' : ''
    }
    if cmd[4]=='reset' :
        response['result']['control']=cmd[4]
        # response before reset
        log.error('received RESET command')
        t = threading.Timer(5, reboot)
        t.start()
    if cmd[4] == 'killprocess':
        response['result']['control']=cmd[4]
        log.warn('received kill process')
        subprocess.call(['kill', str(os.getpid())])
    elif cmd[4]=='volume' :
        response['result']['control']=cmd[4]
        response['result']['value']=cmd[5]
        log.debug('set volume to ' + cmd[5])
        gPlaySound.setVolume( int(cmd[5]) )
        gPlaySound.writeVolume( cmd[5] )
    elif cmd[4]=='led' :
        response['result']['control']=cmd[5]
        response['result']['value']=cmd[6]
        ctrlLed(cmd[5], int(cmd[6]))
#    elif cmd[4]=='timer' and cmd[5]=='kill':
#        timer.clearTimer()
    else : 
        err = 404
        response={'status':'0'}
    return err, response
        
def getDeviceControl(cmd):
    logging.info(cmd)
    err = 200
    retDict = {
        'status': '1',
        'result': { 'control': '',
                    'value': ''
                    },
        'error': ''
    }
    if len(cmd) < 4:
        return 404
    if cmd[4]=='volume':
        retDict['result']['control'] = cmd[4]
        retDict['result']['value'] = gPlaySound.getVolume()
    elif cmd[4]=='led' :
        retDict['result']['control'] = cmd[4]
        retDict['result']['value'] = gpioCtrl.getGpioStatusAll()
    elif cmd[4]=='capture':
        retDict['result']['control'] = cmd[4]
        camera = gProcesses.process.gDetectPR
        filename = camera.imageWrite('get', camera.stream.read())
        imgfile = '/home/inno/output/' + filename
        subprocess.check_output('mv ' + imgfile + ' /var/www/html/capture/' +
                                filename, shell=True)
        url='http://' + getLprSysInfo()['ipaddr'] + ':80/capture/' + filename
        retDict['result']['value'] = url
    elif cmd[4]=='swver':
        retDict['result']['control'] = cmd[4]
        ver = subprocess.check_output('cat /root/VERSION', shell=True)
        retDict['result']['value'] = ver.decode().strip()
    elif cmd[4] == 'parkingin':
        retDict['result']['control'] = cmd[4]
        ver = subprocess.check_output('cat /var/parkingin', shell=True)
        retDict['result']['value'] = ver.decode().strip()
        
    else : 
        err = 404
    return err, retDict

def setDeviceSettings(cmd):
    logging.info(cmd)
    sysinfo=getLprSysInfo()
    log.info('cmd length=' + str(len(cmd)))
    if len(cmd)==5 :
        retDict[cmd[3]] = cmd[4]
        for i in range(len(cmd)) :
            retDict[cmd[3]] = cmd[4]
            logging.info(retDict[cmd[3]] + " = " + cmd[4])
    else:
        retDict = {
            "status" : "0", # false or true
            "result" : {
                 "device_id" : sysinfo['device_id'],
#             "penalty_time" : str(int(config.getConfig('penalty_time'))*60), # 초단위
                 "penalty_time" : '10',
                 "warnings" : config.getConfig('setting', 'warnings'), # 경고방송 회수
                 "warnings" : '3',
                 "sync_period_time" : config.getConfig('setting', 'sync_period_time'),  # 세팅값 변경주기 
                 "wlight_start_time" : config.getConfig('setting', 'wlight_start_time'),
                 "wlight_end_time" : config.getConfig('setting', 'wlight_end_time'),  
            },
            "error" : "error message" # if status false
        }
    return retDict
    
def getChargerStatus(path, param):
    global statusList
    global oldChargerStatus
    print('getChargerStatus function')
    print(path)
    err=''
#        if path[3]=='0,0' or path[3]:
    if '0' in path[3]:
        log.info('[charger] received initial status')
        statusList=[]
        oldChargerStatus='0'
    else:
        path[3].replace('9', '1')  # 9 == 이전사용자가 충전완료 후 완료버튼을 누르지 않은 상태. 충전완료이므로 1(충전대기)로 처리.
        lengthOfStatus = len(statusList)
        if lengthOfStatus==0:
            if path[3]=='2,2':
                log.info('[charger] received first status ' + path[3] + ', it will be ignored')
#            elif status=='5' or status=='4' or status=='3':
#                log.info('[charger] first status is error!! set status.')
#                oldChargerStatus='0'
#                status='5'
            else:
                statusList.append(path[3])
                timer.chargerStatus=0
                log.info('[charger] received first status' + statusList[0] + \
                        'timer.chargerStatus=' + str(timer.chargerStatus) )
        elif lengthOfStatus==1 and statusList[0]!=path[3]:
            if ((statusList[0]=='1,1' and (path[3]=='2,1' or path[3]=='1,2' or path[3]=='2,2')) or 
                (statusList[0]=='1,2' and (path[3]=='2,2' or path[3]=='2,1')) or
                (statusList[0]=='2,1' and (path[3]=='2,2' or path[3]=='1,2')) or
                (statusList[0]=='5,1' and (path[3]=='5,2'))) :
                
                statusList.append(path[3])
                log.warn('[charger] received second status' + statusList[1])
                timer.chargerStatus=2
                chargerEvent.set()
            elif ((statusList[0]=='1,2' and path[3]=='1,1') or
                    (statusList[0]=='2,1' and path[3]=='1,1')) :
                statusList[0]='1,1'
                log.info('[charger] received second status ' + path[3] + ', it will go first status')
        elif lengthOfStatus==2 and statusList[1]!=path[3]:
            if (
                (path[3]=='1,1' and ((statusList[0]=='1,1' and statusList[1]=='2,1') or
                                    (statusList[0]=='1,1' and statusList[1]=='1,2') or
                                    (statusList[0]=='1,1' and statusList[1]=='2,2') or
                                    (statusList[0]=='1,2' and statusList[1]=='2,2') or
                                    (statusList[0]=='1,2' and statusList[1]=='2,1') or
                                    (statusList[0]=='2,1' and statusList[1]=='2,2') or
                                    (statusList[0]=='2,1' and statusList[1]=='1,2')))
                or
                (path[3]=='1,2' and ((statusList[0]=='1,1' and statusList[1]=='2,1') or
                                    (statusList[0]=='1,1' and statusList[1]=='2,2') or
                                    (statusList[0]=='1,1' and statusList[1]=='1,2')))
                or
                (path[3]=='2,1' and ((statusList[0]=='1,2' and statusList[1]=='2,2') or
                                    (statusList[0]=='1,1' and statusList[1]=='1,2') or
                                    (statusList[0]=='1,1' and statusList[1]=='2,2') or
                                    (statusList[0]=='2,1' and statusList[1]=='2,2')))
                or
                (path[3]=='5,1' and ((statusList[0]=='5,1' and statusList[1]=='5,2')))
                ) :
                statusList.append(path[3])
                log.warn('[charger] received third status' + statusList[2])
                timer.chargerStatus=1
                chargerEvent.set()
#        if timer.mainChargerStatus=='1':
#            log.debug("timer.mainChargerStatus=0. it is init status.")
#            status='1'
        status = path[3].split(',')[1]
        log.warn('old=' + oldChargerStatus + ", status=" + status)
        if oldChargerStatus != status : # it will send to server charger status only
            oldChargerStatus = status
            """
            if status=='5' or status=='4' or status=='3':
                log.error('received charger status error!!!!!' + status)
                timer.mainChargerStatus=13
                chargerEvent.set()
            """
            if status=='3':
                log.error('received charger status error!!!!!' + status)
                timer.mainChargerStatus=13
                chargerEvent.set()
            elif status=='4':
                log.error('received charger status error!!!!!' + status)
                timer.mainChargerStatus=14
                chargerEvent.set()
            elif status=='5':
                log.error('received charger status error!!!!!' + status)
                timer.mainChargerStatus=15
                chargerEvent.set()
            elif status=='9':
                log.error('received charger status error!!!!!' + status)
                timer.mainChargerStatus=16
                chargerEvent.set()
            elif status=='1':
                timer.mainChargerStatus=12
                chargerEvent.set()
            elif status=='2':
                timer.mainChargerStatus=11
                chargerEvent.set()
 
    retDict = {'status':timer.chargerStatus, 'error':err}
    return retDict
dictApiForServer = {
    '/device/status/' : getDeviceStatus,        # 
    '/device/status/set/' : setDeviceControl,
    '/device/status/get/' : getDeviceControl,
    '/device/settings/' : setDeviceSettings,
    '/charger/status/'  : getChargerStatus,
}
def doUpdate():
    log.error("!!!!!!!!! received update !!!!!!!!!")
    os.chdir('/root/')
    subprocess.check_output(['/root/g-update.sh'])
#    subprocess.check_output(['reboot'])
class S(BaseHTTPRequestHandler):
    def _set_response(self, code, response):
        self.send_response(code)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        if code==200:
#            self.wfile.write("request for {}".format(self.path).encode('utf-8'))
#            self.wfile.write(response.encode('utf-8'))
#            self.wfile.write(json.dumps(response))
            self.wfile.write(str(response).encode('utf-8'))
        if code==404:
            self.wfile.write("404 Not Found".encode('utf-8'))
    def do_GET(self):
        logging.info("GET request,\nPath: %s\nHeaders:\n%s\n", str(self.path), str(self.headers))
        logging.info("-"*50)
        path=str(self.path)
        logging.info( path )
        err=200
        resp=''
        param=''
        # identity
        if '/device/status/' in path :
            path=str(self.path).split('/')
            if path[3]=='set':
                err, resp=setDeviceControl(path)
            elif path[3]=='get':
                err, resp=getDeviceControl(path)
                print('get resp=', resp)
            else:
                resp=getDeviceStatus('')
        elif '/device/settings/' in path : 
            path=str(self.path).split('/')
            resp=setDeviceSettings(path)
        elif '/charger/status/' in path :
            path=str(self.path).split('/')
            resp=getChargerStatus(path, param)
        elif '/letsUpdate/' in path :
            resp = {
                'ip': subprocess.check_output(['hostname', '-I'])\
                      .decode().split()[0],
                'old_version': subprocess.check_output(['cat', '/root/VERSION'])\
                               .decode()
            }
            doUpdate()
            resp['updated_version'] =\
                subprocess.check_output(['cat', '/root/VERSION']).decode()
            self._set_response(err, json.dumps(resp))
            
            subprocess.check_output(['sync'])
        else :
            err=404
        self._set_response(err, json.dumps(resp))
    def do_POST(self):
        content_length = int(self.headers['Content-Length']) # <--- Gets the size of data
        post_data = self.rfile.read(content_length) # <--- Gets the data itself
        logging.info("POST request,\nPath: %s\nHeaders:\n%s\n\nBody:\n%s\n",
                str(self.path), str(self.headers), post_data.decode('utf-8'))
        path=str(self.path)
        logging.info( path )
        err=200
        # identity
        if '/device/status/' in path :
            path=str(self.path).split('/')
            dictApiForServer[self.path](cmd)
        elif '/device/settings/' in path :
            dictApiForServer[self.path](cmd, param)
        else :
            err=404
        self._set_response(err)
#        self.wfile.write("POST request for {}".format(self.path).encode('utf-8'))
server_address = ('', 8080)
httpd = HTTPServer(server_address, S)
pid=os.getpid()
#def run(server_class=HTTPServer, handler_class=S, port=8080):
def run():
    logging.basicConfig(level=logging.DEBUG)
    logging.info('Starting httpd...\n')
    print('pid in run=', pid)
    try:
        httpd.serve_forever()
        print('server forever')
    except KeyboardInterrupt:
        print('keyboard interrupt')
        closeServer()
        pass
    except Exception :
        print('exception occured')
        pass
def closeServer():
    os.system('kill ' + str(pid))
    httpd.server_close()
    logging.info('Stopping httpd...\n')
if __name__ == '__main__':
    from sys import argv
    if len(argv) == 2:
        run(port=int(argv[1]))
    else:
        run()