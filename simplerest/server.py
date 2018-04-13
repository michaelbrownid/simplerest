from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler
from SocketServer import ThreadingMixIn
import urlparse
import time
import cgi
import SimpleFileResponse
import sys
import os
from StringIO import StringIO

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
        
        if not hasattr(self,"message"): self.message=""

        self.message += self.__doc__
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
        """

        if not hasattr(self,"message"): self.message=""
        print "uploadFile"
        self.message += "self.form" + str(self.form) + "\n"
        print self.message
        for kk in self.form.keys():
            # convention naming for files from do_POST: "_file.<key>.<filename>" convention
            if "_file." in kk:
                print "writing file %s" % kk
                infile = self.form[kk]
                with file(kk,'wb') as f:
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
    def action_exit( self ):
        """Kill the server with a sys.exit(0). Doesn't really work as blocked threads are still spawned"""
        sys.exit(0)

    ################################
    def action_exec( self ):
        """Take field "value", exec it, print stdout

        192.168.11.16:8080/exec?value=print+\"hi\"
        """

        toexec = self.form["value"][0]

        print "exec: toexec=%s" % toexec

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

        print "exec: toexec=%s" % toexec

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

        print "*** setkey", mykey, myvalue

        keystate[mykey]="new"
        keyvalue[mykey]=myvalue

        self.message = "done setkey %s %s" % (mykey,myvalue)

    ################################
    def action_getkey( self ):
        """Take field key and return value"""

        mykey = self.form["key"][0]
        print "*** getkey", mykey

        if mykey not in keystate:
            self.httpstatus = 404
            self.message = "error mykey not in keystate"
            print self.message
            return()

        # possible blocking long poll
        if not "immediate" in self.form:
            while not keystate[mykey]=="new":
                #print("sleep")
                time.sleep(0.1)

        # return the value
        self.message = "%s" % (keyvalue[mykey])
        print self.message
        keystate[mykey] = "old"

    ################################
    def handleRequest(self):
        print "***handleRequest"

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
        self.wfile.write(self.message)
        self.wfile.write('\n')

    ################################
    def do_OPTIONS(self):
        """Chrome if making request with non-standard headers (ie basic
authentication) will make a "preflight" OPTIONS request. To allow
cross site return CORS"""
        print "***do_OPTIONS"
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*") # CORS for cross-origin xhr if needed
        self.end_headers()

    ################################
    def do_GET(self):
        print "***do_GET"

        if "form" in dir(self): print "error do_POST: form already exists!"

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
        print "***do_POST"

        # parse post values into form and then pass to do_GET for processing

        #print "rfile", self.rfile.read(int(self.headers.getheader('Content-Length')))

        self.environ={}

        if "form" in dir(self): print "error do_POST: form already exists!"
        self.form={}

        if True:
            messedup = cgi.FieldStorage( fp=self.rfile,headers=self.headers, environ={'REQUEST_METHOD':'POST'})
            #print "messedup", str(messedup)
            for mm in messedup:
                #print "mm", mm
                #print "messedup[mm]", str(messedup[mm])

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
                        key.filename=""
                        mykey = ""+mm+key.filename
                        self.form[mykey] = key.value
                    else:
                        # passed as file type object. fieldstorage already
                        # dumped to file and gives pointer to
                        # .file. calling key.value will read into
                        # memory. pass .file with name
                        # "_file_key_filename" convention
                        mykey = "_file."+mm+"."+key.filename
                        self.form[mykey] = key.file
                        
            #print self.form

        self.handleRequest()


################################
class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in a separate thread."""

################################
if __name__ == '__main__':
    args = {"d": "./", "p": 8080, "h": "192.168.11.16"}
    ii=1
    while ii<len(sys.argv):
        if sys.argv[ii] == "d":
            ii+=1
            args["d"] = sys.argv[ii]
            ii+=1
        elif sys.argv[ii] == "p":
            ii+=1
            args["p"] = int(sys.argv[ii])
            ii+=1
        elif sys.argv[ii] == "h":
            ii+=1
            args["h"] = sys.argv[ii]
            ii+=1
        else:
            print "unknown option", sys.argv
    print "args", args

    # change to root directory
    os.chdir(args["d"])

    #server = ThreadedHTTPServer(('localhost', 8080), RestHandler)
    server = ThreadedHTTPServer((args["h"], args["p"]), RestHandler)
    print('Starting server, use <Ctrl-C> to stop')
    server.serve_forever()
