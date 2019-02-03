##PYTHON2: from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler
from http.server import HTTPServer, BaseHTTPRequestHandler
##PYTHON2: from SocketServer import ThreadingMixIn
from socketserver import ThreadingMixIn
##PYTHON2: import urlparse
import urllib.parse as urlparse
import time
import cgi
from . import SimpleFileResponse
import sys
import os
from io import StringIO
import argparse
import threading
import requests
from . import broadcast
import socket

################################
# global state variables shared between threads
global keystate
global keyvalue
keystate = {} # new, old
keyvalue = {}

################################
class RestHandler(BaseHTTPRequestHandler):    
    """RestHandler: respond to both HTTP GET and POST requests with parameter variables.

    For any function defined with name "action_NAME", requests to "GET server/NAME" will execute action_NAME()

    self.path is the full requested path

    self.form["key"][0] gets the value of "key" of the passed parameter variables

    self.message is the returned to the requester

    Run as:
        python restPython # on port 8080

    Or run as subclass after installing simple rest with:
       "pip install git+https://github.com/michaelbrownid/simplerest.git"

        import simplerest.server
        class myHandler(simplerest.server.RestHandler):
            def action_myfunction( self ):
                self.message = "myfunction here!"
        server = simplerest.server.ThreadedHTTPServer(('localhost', 9000), myHandler)
        print('Starting server, use <Ctrl-C> to stop')
        server.serve_forever()

       http://localhost:9000/myfunction now returns "myfunction here!"

    """

    ################################
    def actionsIn( self, mypath ):
        # get list of actions
        actions={}
        for xx in dir(self):
            if "action_" in xx:
                actions[xx.replace("action_","")] = getattr(self,xx)
        for xx in actions.keys():
            # look for action in self.path "/service?foo=bar" with optional "?" parmaters
            mypath+="?" # put "?" on end for code ease. OK if there's already one there as find gets first
            if mypath[:mypath.find("?")] == "/%s" % xx:
                return(actions[xx])
        return(None)

    ################################
    def action_help( self ):
        """help: list available commands"""
        
        if not hasattr(self,"message"): self.message=""

        self.message += "\n #### list of commands:\n"

        for xx in dir(self):
            if "action_" in xx:
                self.message += "\n #### %s:\n%s\n" % (xx, getattr(self,xx).__doc__)
                
    ################################
    def action_uploadFile( self ):
        """Upload possible multiple files from browser using POST

        From do_POST: all uploaded files will be self.form["uploadedFile<filename>]

        HTML:
        <form method="post" action="http://192.168.11.16:8080/uploadFile" enctype="multipart/form-data">
        <input name="filesToUpload" id="filesToUpload" type="file" multiple="" />
	<input type="submit" value="Submit">
        </form>

        PYTHON send report.xls:
        with open('report.xls', 'rb') as f: r = requests.post('http://192.168.11.16:8080/uploadFile', files={'MYUPLOAD': f})
        # server will save as _file.MYUPLOAD.report.xls

        CURL send report.xls:
        curl -v -F "MYUPLOAD=@report.xls" http://192.168.11.207:8080/uploadFile
        """

        if not hasattr(self,"message"): self.message=""
        print("uploadFile")
        self.message += "self.form" + str(self.form) + "\n"
        print(self.message)
        for kk in self.form.keys():
            # convention naming for files from do_POST: "_file.<key>.<filename>" convention
            if "_file." in kk:
                print("writing file %s" % kk)
                infile = self.form[kk]
                with open(kk,'wb') as f:
                    chunk_size=1024
                    data = infile.read(chunk_size)
                    while data:
                        f.write(data)
                        data = infile.read(chunk_size)
                        
        self.message += "files written"

    ################################
    def action_deleteFile( self ):
        """Delete file.
        http://192.168.11.16:8080/deleteFile?value=filesToUploadfoo.txt
        current just prints command but does not execute
        """

        if not hasattr(self,"message"): self.message=""

        self.message += "deleteFile\n"

        todelete = self.form["value"][0]

        if todelete[0] == "/" or ".." in todelete:
            self.message += "Cannot delete outside local directory %s" % todelete
            return

        cmd = "rm %s/%s" % (os.getcwd(),todelete)
        self.message+=cmd
        self.message+="command constructed but no executed"

    ################################
    def filepodFind( self, finddir ):
        """output filename, mtime, and size just like:
        find . -type f -printf "%P\t%T@\t%s\n"
        """

        result = []
        if finddir[-1]!="/": finddir = finddir+"/"
        rootlen=-1
        for root, dirs, files in os.walk(finddir):
            if rootlen==-1: rootlen=len(root)
            for item in files:
                if root[-1]=="/":
                    fn= "%s%s" % (root, item)
                else:
                    fn= "%s/%s" % (root, item)

                ok = True
                try:
                    size = os.path.getsize(fn)
                except:
                    ok = False
                if ok:
                    mtime = int(os.path.getmtime(fn)+0.5)
                    result.append( "%s\t%d\t%d" % (fn[rootlen:], mtime, size) )
        return(result)
        
    def action_findFiles( self ):
        """Find all files under directory
        http://192.168.11.16:8080/findFiles?value=/var/log;outfile=filelist.txt
        outfile is optional
        """

        if not hasattr(self,"message"): self.message=""

        self.message += "findFiles_begin\n"

        mydir = self.form["value"][0]
        if not os.path.exists(mydir):
            self.message += "ERROR! %s does not exist!" % (mydir)
            return
        
        allfiles = self.filepodFind( mydir )
        
        if not "outfile" in self.form:
            # output in http response
            self.message += "\n".join(allfiles)
            self.message += "\n"
        else:
            # output to file
            if os.path.exists(self.form["outfile"][0]):
                self.message += "ERROR! %s already exists!" % (self.form["outfile"][0])
            else:
                ofp=open(self.form["outfile"][0],"w")
                print ("\n".join(allfiles), file=ofp)
                print ("\n", file=ofp)
                ofp.close()
        self.message += "fileFiles_end"
        
    ################################
    def action_exit( self ):
        """Kill the server with a sys.exit(0). Doesn't really work as blocked threads are still spawned"""
        sys.exit(0)

    ################################
    def action_exec( self ):
        """Take field "value", exec it, print stdout

        192.168.11.16:8080/exec?value=print+\"hi\"
        """

        toexec = self.form["value"][0]

        print("exec: toexec=%s" % toexec)

        # execute capturing stdout
        buffer = StringIO()
        sys.stdout = buffer
        exec(toexec)
        sys.stdout = sys.__stdout__

        self.message = "done exec.\n----- toexec\n%s\n---- stdout\n%s----\n" % (toexec, buffer.getvalue())

    ################################
    def action_execFile( self ):
        """Load file from field "value", exec it, print stdout"""

        toexec = open(self.form["value"][0]).read()

        print("exec: toexec=%s" % toexec)

        # execute capturing stdout
        buffer = StringIO()
        sys.stdout = buffer
        exec(toexec)
        sys.stdout = sys.__stdout__

        self.message = "done execFile.\n----- toexec\n%s\n---- stdout\n%s----\n" % (toexec, buffer.getvalue())
        
    ################################
    def action_setkey( self ):
        """Take fields key and value and set"""

        # update global state
        mykey = self.form["key"][0]
        myvalue = self.form["value"][0]

        keystate[mykey]="new"
        keyvalue[mykey]=myvalue

        self.message = "done setkey %s %s" % (mykey,myvalue)

    ################################
    def setkey_direct( self, mykey, myvalue):
        """A helper function to action_setkey. So rather than direct access
        simplerest.server.keystate[mykey]="new"
        simplerest.server.keyvalue[mykey]=myval
        in Python code, one can call self.setkey_direct(mykey,myval)"""

        keystate[mykey]="new"
        keyvalue[mykey]=myvalue

    ################################
    def action_getkey( self ):
        """Take field key and return value"""

        mykey = self.form["key"][0]
        print("*** getkey", mykey)

        if mykey not in keystate:
            self.httpstatus = 404
            self.message = "error mykey not in keystate"
            print(self.message)
            return()

        # possible blocking long poll. Probably dangerous for large number of "old" keys
        if not "immediate" in self.form:
            while not keystate[mykey]=="new":
                #print("sleep")
                time.sleep(0.1)

        # return the value
        self.message = "%s" % (keyvalue[mykey])
        keystate[mykey] = "old"

    ################################
    def getkeystate( self, mykey ):
        return( keystate[mykey] )

    def getkeyvalue( self, mykey ):
        return( keyvalue[mykey] )

    ################################
    def handleRequest(self):
        print("***handleRequest")

        ################################
        #print(dir(self))
        #print(self.__dict__)
        # path:/service?foo=bar
        # form:["foo=['bar'];"]
        # environ:{'QUERY_STRING': 'foo=bar', 'REQUEST_METHOD': 'GET'}
        # ['MessageClass', '__doc__', '__init__', '__module__', 'address_string', 'client_address', 'close_connection', 'command', 'connection', 'date_time_string', 'default_request_version', 'disable_nagle_algorithm', 'do_GET', 'do_POST', 'end_headers', 'environ', 'error_content_type', 'error_message_format', 'finish', 'form', 'handle', 'handleRequest', 'handle_one_request', 'headers', 'log_date_time_string', 'log_error', 'log_message', 'log_request', 'monthname', 'parse_request', 'path', 'protocol_version', 'raw_requestline', 'rbufsize', 'request', 'request_version', 'requestline', 'responses', 'rfile', 'send_error', 'send_header', 'send_response', 'server', 'server_version', 'setup', 'sys_version', 'timeout', 'version_string', 'wbufsize', 'weekdayname', 'wfile']
        # {'requestline': 'GET /service?foo=bar HTTP/1.1', 'wfile': <socket._fileobject object at 0x7f8b0afdd350>, 'form': {'foo': ['bar']}, 'request': <socket._socketobject object at 0x7f8b0b018f30>, 'raw_requestline': 'GET /service?foo=bar HTTP/1.1\r\n', 'server': <__main__.ThreadedHTTPServer instance at 0x7f8b0d117fc8>, 'headers': <mimetools.Message instance at 0x7f8b0afe7bd8>, 'connection': <socket._socketobject object at 0x7f8b0b018f30>, 'command': 'GET', 'rfile': <socket._fileobject object at 0x7f8b0b036450>, 'path': '/service?foo=bar', 'environ': {'QUERY_STRING': 'foo=bar', 'REQUEST_METHOD': 'GET'}, 'request_version': 'HTTP/1.1', 'client_address': ('127.0.0.1', 50797), 'close_connection': 1}

        ################################
        doit = self.actionsIn( self.path )

        # if not command to be executed then send the file
        if doit is None:
            SimpleFileResponse.SimpleFileResponse( inrequestarg=self )

            # message_parts = [
            #     'path:%s' % self.path,
            #     'form:%s' % [ "%s=%s;" % (k,self.form[k]) for k in self.form.keys()],
            #     'environ:%s' % self.environ
            # ]
            # self.send_response(200)
            # self.end_headers()
            # self.wfile.write("default response\n")
            # self.wfile.write(message_parts)
            # self.wfile.write('\n')

            return

        # doit and return response message from action
        doit()
        if not hasattr(self,"httpstatus"): self.httpstatus=200
        self.send_response(self.httpstatus)
        self.end_headers()
        self.wfile.write(str.encode(self.message))
        self.wfile.write(str.encode('\n'))

    ################################
    def do_OPTIONS(self):
        """Chrome if making request with non-standard headers (ie basic
authentication) will make a "preflight" OPTIONS request. To allow
cross site return CORS"""
        print("***do_OPTIONS")
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*") # CORS for cross-origin xhr if needed
        self.end_headers()

    ################################
    def do_GET(self):
        print("***do_GET")

        if "form" in dir(self): print("error do_POST: form already exists!")

        # THIS IS MESSED UP! To use FieldStorage on GET, you have
        # to pull out the GET variables yourself with urlparse!
        # Should be transparent!
        self.environ={'REQUEST_METHOD':'GET', 'QUERY_STRING': urlparse.urlparse(self.path).query}
        #self.form = dict([p.split("=") for p in urlparse.urlparse(self.path).query.split("&")])
        self.form = urlparse.parse_qs( urlparse.urlparse(self.path).query )

        self.handleRequest()

    ################################
    def do_POST(self):

        """process POST variables into environ and pass to do_GET for handling

        """
        print("***do_POST")

        # parse post values into form and then pass to do_GET for processing

        #print("rfile", self.rfile.read(int(self.headers.getheader('Content-Length'))))

        self.environ={}

        if "form" in dir(self): print("error do_POST: form already exists!")
        self.form={}

        if True:
            messedup = cgi.FieldStorage( fp=self.rfile,headers=self.headers, environ={'REQUEST_METHOD':'POST'})
            #print("messedup", str(messedup))
            for mm in messedup:
                #print("mm", mm)
                #print("messedup[mm]", str(messedup[mm]))

                if isinstance(messedup[mm],list):
                    # list of things with same name
                    for key in messedup[mm]:
                        if key.filename is None:
                            # passed as simple string
                            key.filename=""
                            mykey = ""+mm+key.filename
                            self.form[mykey] = key.value
                        else:
                            # passed as file type object. fieldstorage already
                            # dumped to file and gives pointer to
                            # .file. calling key.value will read into
                            # memory. pass .file with name
                            # "_file.key.filename" convention
                            mykey = "_file."+mm+"."+key.filename
                            self.form[mykey] = key.file
                else:
                    # just single name, not list
                    key = messedup[mm]
                    if key.filename is None:
                        # passed as simple string
                        if mm is None: mm="UPLOAD"
                        mykey = ""+mm
                        self.form[mykey] = key.value
                    else:
                        # passed as file type object. fieldstorage already
                        # dumped to file and gives pointer to
                        # .file. calling key.value will read into
                        # memory. pass .file with name
                        # "_file_key_filename" convention
                        mykey = "_file."+mm+"."+key.filename
                        self.form[mykey] = key.file
                        
            #print(self.form)

        self.handleRequest()


################################
class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in a separate thread."""

################################
def main( args ):

    # change to root directory
    os.chdir(args["dir"])

    server = ThreadedHTTPServer((args["host"], args["port"]), RestHandler)

    # start a thread with the server --that thread will then start one more thread for each request
    server_thread = threading.Thread(target=server.serve_forever)
    # Exit the server thread when the main thread terminates
    server_thread.daemon = True
    server_thread.start()
    print("Server loop running in thread:", server_thread.name)

    #alternative that blocks:
    #print('Starting server, use <Ctrl-C> to stop')
    #server.serve_forever()

    #### handle UDP broadcast
    if args["broadcast"]=="1":
        # set the key on the server started above so we know when to stop. (could I call setkey_direct function in server??)
        requests.get("http://localhost:%d/setkey?key=broadcast&value=1" % args["port"])
        
        mycast = broadcast.sender(6789,args["port"])

        # while no one has changed the key from "1" keep going. sleep so no spin
        while "1" in requests.get("http://localhost:%d/getkey?key=broadcast&immediate=T" % args["port"]).text:
            print("broadcasting on port 6789")
            mycast.send()
            time.sleep(1.0)

        print("broadcast stopped")

    # wait on server thread, otherwise will terminate killing server thread
    server_thread.join()

################################
if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument('--dir', help='the directory to serve from', default="./")
    parser.add_argument('--port', help='the port to serve on', default=8080)
    parser.add_argument('--host', help='the host to serve on', default="0.0.0.0")
    parser.add_argument('--broadcast', help='broadcast on start 0/1. /setkey?key=broadcast&value=0 to turn off', default="0")
    args = parser.parse_args()

    # try to find ip so don't necessarily need broadcast
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    print("ipAddress",s.getsockname()[0])
    s.close()
    
    main(vars(args)) # vars gives dict rather than dotted so I run
                     # main with simple dict outside main: main(
                     # {"dir":"foobar"}). class is too verbose
