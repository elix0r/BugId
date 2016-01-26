import os, re, sys, threading;
from dxConfig import dxConfig;
sBaseFolderPath = os.path.dirname(__file__);
sys.path.extend([os.path.join(sBaseFolderPath, x) for x in ["src", "modules"]]);
from cBugId import cBugId;
from sOSISA import sOSISA;
from cErrorReport_foSpecialErrorReport_STATUS_ACCESS_VIOLATION import ddtsDetails_uAddress_sISA;

bDebugStartFinish = False;
bDebugIO = False;
uSequentialTests = 32; # >32 will probably not work.

dxBugIdConfig = dxConfig["BugId"];
if bDebugIO:
  dxBugIdConfig["bOutputStdIO"] = True;
dxBugIdConfig["bOutputStdErr"] = False;
dxBugIdConfig["bOutputProcesses"] = False;

asTestISAs = [sOSISA];
if sOSISA == "x64":
  asTestISAs.append("x86");

sBaseFolderPath = os.path.dirname(__file__);
dsBinaries_by_sISA = {
  "x86": os.path.join(sBaseFolderPath, r"Tests\bin\Tests_x86.exe"),
  "x64": os.path.join(sBaseFolderPath, r"Tests\bin\Tests_x64.exe"),
};

bFailed = False;
oOutputLock = threading.Lock();
# If you see weird exceptions, try lowering the number of parallel tests:
oConcurrentTestsSemaphore = threading.Semaphore(uSequentialTests);
class cTest(object):
  def __init__(oTest, sISA, asCommandLineArguments, srBugId):
    oTest.sISA = sISA;
    oTest.asCommandLineArguments = asCommandLineArguments;
    oTest.srBugId = srBugId;
    oTest.bInternalException = False;
  
  def __str__(oTest):
    return "%s =%s=> %s" % (" ".join(oTest.asCommandLineArguments), oTest.sISA, oTest.srBugId);
  
  def fRun(oTest):
    global bFailed, oOutputLock;
    oConcurrentTestsSemaphore.acquire();
    sBinary = dsBinaries_by_sISA[oTest.sISA];
    asApplicationCommandLine = [sBinary] + oTest.asCommandLineArguments;
    if bDebugStartFinish:
      oOutputLock.acquire();
      print "@ Started %s" % oTest;
      oOutputLock.release();
    try:
      oTest.oBugId = cBugId(
        asApplicationCommandLine = asApplicationCommandLine,
        fFinishedCallback = oTest.fFinishedHandler,
        fInternalExceptionCallback = oTest.fInternalExceptionHandler,
      );
    except Exception, oException:
      if not bFailed:
        bFailed = True;
        oOutputLock.acquire();
        print "- %s" % oTest;
        print "    => Exception: %s" % oException;
        oOutputLock.release();
  
  def fWait(oTest):
    hasattr(oTest, "oBugId") and oTest.oBugId.fWait();
  
  def fFinished(oTest):
    if bDebugStartFinish:
      oOutputLock.acquire();
      print "@ Finished %s" % oTest;
      oOutputLock.release();
    oConcurrentTestsSemaphore.release();
  
  def fFinishedHandler(oTest, oErrorReport):
    global bFailed, oOutputLock;
    if not bFailed:
      oOutputLock.acquire();
      if oTest.srBugId:
        if not oErrorReport:
          print "- %s" % oTest;
          print "    => got no error";
          bFailed = True;
        elif not re.match("^([0-9A-F_#]{2})+ (%s) .+\.exe!.*$" % re.escape(oTest.srBugId), oErrorReport.sId):
          print "- %s" % oTest;
          print "    => %s (%s)" % (oErrorReport.sId, oErrorReport.sErrorDescription);
          bFailed = True;
        else:
          print "+ %s" % oTest;
      elif oErrorReport:
        print "- %s" % oTest;
        print "    => %s (%s)" % (oErrorReport.sId, oErrorReport.sErrorDescription);
        bFailed = True;
      else:
        print "+ %s" % oTest;
      if bFailed:
        print "    Command line: %s" % " ".join([dsBinaries_by_sISA[oTest.sISA]] + oTest.asCommandLineArguments);
      oOutputLock.release();
    oTest.fFinished();
  
  def fInternalExceptionHandler(oTest, oException):
    global bFailed;
    oTest.fFinished();
    if not bFailed:
      oOutputLock.acquire();
      bFailed = True;
      print "@ Exception in %s: %s" % (oTest, oException);
      oOutputLock.release();
      raise;

if __name__ == "__main__":
  aoTests = [];
  for sISA in asTestISAs:
    sMinusOne = {"x86": "FFFFFFFF", "x64": "FFFFFFFFFFFFFFFF"}[sISA];
    sMinusTwo = {"x86": "FFFFFFFE", "x64": "FFFFFFFFFFFFFFFE"}[sISA];
    aoTests.append(cTest(sISA, ["AccessViolation", "READ", "1"], "AVR:NULL+ODD"));
    aoTests.append(cTest(sISA, ["AccessViolation", "READ", "2"], "AVR:NULL+EVEN"));
    aoTests.append(cTest(sISA, ["AccessViolation", "READ", sMinusOne], "AVR:NULL-ODD"));
    aoTests.append(cTest(sISA, ["AccessViolation", "READ", sMinusTwo], "AVR:NULL-EVEN"));
    aoTests.append(cTest(sISA, ["Breakpoint"], "Breakpoint"));
    aoTests.append(cTest(sISA, ["C++"], "C++:cException"));
    aoTests.append(cTest(sISA, ["IntegerDivideByZero"], "IntegerDivideByZero"));
    aoTests.append(cTest(sISA, ["Numbered", "41414141", "42424242"], "0x41414141"));
    aoTests.append(cTest(sISA, ["IllegalInstruction"], "IllegalInstruction"));
    aoTests.append(cTest(sISA, ["PrivilegedInstruction"], "PrivilegedInstruction"));
    aoTests.append(cTest(sISA, ["StackExhaustion"], "StackExhaustion"));
    aoTests.append(cTest(sISA, ["RecursiveCall"], "RecursiveCall"));
    aoTests.append(cTest(sISA, ["StaticBufferOverrun10", "Write", "20"], "FailFast2:StackCookie"));
    aoTests.append(cTest(sISA, ["OutOfBounds", "Heap", "Write", "c", "-1"], "HeapCorrupt"));  # Write the byte at offset -1 from the start of the buffer.
    aoTests.append(cTest(sISA, ["OutOfBounds", "Heap", "Write", "c", "d"], "HeapCorrupt"));   # Write the byte at offset 0 from the end of the buffer.
    if sISA not in ["x86"]:
      # x86 test results in "0BA2 FailFast2:AppExit Tests_x86.exe!abort (A critical issue was detected (code C0000409, fail fast code 7: FAST_FAIL_FATAL_APP_EXIT))"
      aoTests.append(cTest(sISA, ["PureCall"], "PureCall"));
      # Page heap does not appear to work for x86 tests on x64 platform.
      aoTests.append(cTest(sISA, ["UseAfterFree", "Read", "20", "0"], "AVR:Free"));
      aoTests.append(cTest(sISA, ["UseAfterFree", "Write", "20", "0"], "AVW:Free"));
      aoTests.append(cTest(sISA, ["BufferOverrun", "Heap", "Read", "20", "4"], "AVR:OOB"));
      aoTests.append(cTest(sISA, ["BufferOverrun", "Heap", "Write", "20", "4"], "AVW:OOB"));
      aoTests.append(cTest(sISA, ["OutOfBounds", "Heap", "Read", "c", "10"], "AVR:OOB"));       # Read byte at offset 0 in the guard page.
      aoTests.append(cTest(sISA, ["OutOfBounds", "Heap", "Read", "c", "11"], "AVR:OOB+ODD"));   # Read byte at offset 1 in the guard page.
      aoTests.append(cTest(sISA, ["OutOfBounds", "Heap", "Read", "c", "12"], "AVR:OOB+EVEN"));  # Read byte at offset 2 in the guard page.
      aoTests.append(cTest(sISA, ["OutOfBounds", "Heap", "Write", "c", "10"], "AVW:OOB"));      # Write byte at offset 0 in the guard page.
      aoTests.append(cTest(sISA, ["OutOfBounds", "Heap", "Write", "c", "11"], "AVW:OOB+ODD"));  # Write byte at offset 1 in the guard page.
      aoTests.append(cTest(sISA, ["OutOfBounds", "Heap", "Write", "c", "12"], "AVW:OOB+EVEN")); # Write byte at offset 2 in the guard page.
    if False:
      # This does not appear to work at all. TODO: fix this.
      aoTests.append(cTest(sISA, ["BufferOverrun", "Stack", "Write", "20", "1000"], "AVW:OOB"));
    
    for uBaseAddress in [(1 << 31) - 1, (1 << 31), (1 << 32), (1 << 47) - 1, (1 << 47), (1 << 63) - 1, (1 << 63)]:
      if uBaseAddress < (1 << 32) or (sISA == "x64" and uBaseAddress < (1 << 47)):
        aoTests.extend([
          cTest(sISA, ["AccessViolation", "Read", "%X" % uBaseAddress], "AVR:Arbitrary"),
          cTest(sISA, ["AccessViolation", "Write", "%X" % uBaseAddress], "AVW:Arbitrary"),
          cTest(sISA, ["AccessViolation", "Call", "%X" % uBaseAddress], "AVE:Arbitrary"),
          cTest(sISA, ["AccessViolation", "Jump", "%X" % uBaseAddress], "AVE:Arbitrary"),
        ]);
      elif sISA == "x64":
        # Above 0x7FFFFFFFFFFF the exception record no longer contains the correct address.
        aoTests.extend([
          cTest(sISA, ["AccessViolation", "Read", "%X" % uBaseAddress], "AV?:Arbitrary"),
          cTest(sISA, ["AccessViolation", "Write", "%X" % uBaseAddress], "AV?:Arbitrary"),
          cTest(sISA, ["AccessViolation", "Call", "%X" % uBaseAddress], "AV?:Arbitrary"),
          cTest(sISA, ["AccessViolation", "Jump", "%X" % uBaseAddress], "AV?:Arbitrary"),
        ]);
  
  for (sISA, dtsDetails_uAddress) in ddtsDetails_uAddress_sISA.items():
    for (uBaseAddress, (sAddressId, sAddressDescription, sSecurityImpact)) in dtsDetails_uAddress.items():
      if uBaseAddress < (1 << 32) or (sISA == "x64" and uBaseAddress < (1 << 47)):
        aoTests.append(cTest(sISA, ["AccessViolation", "Read", "%X" % uBaseAddress], "AVR:%s" % sAddressId));
        aoTests.append(cTest(sISA, ["AccessViolation", "Write", "%X" % uBaseAddress], "AVW:%s" % sAddressId));
        aoTests.append(cTest(sISA, ["AccessViolation", "Call", "%X" % uBaseAddress], "AVE:%s" % sAddressId));
        aoTests.append(cTest(sISA, ["AccessViolation", "Jump", "%X" % uBaseAddress], "AVE:%s" % sAddressId));
      elif sISA == "x64":
        aoTests.append(cTest(sISA, ["AccessViolation", "Read", "%X" % uBaseAddress], "AV?:%s" % sAddressId));
        aoTests.append(cTest(sISA, ["AccessViolation", "Write", "%X" % uBaseAddress], "AV?:%s" % sAddressId));
        aoTests.append(cTest(sISA, ["AccessViolation", "Call", "%X" % uBaseAddress], "AV?:%s" % sAddressId));
        aoTests.append(cTest(sISA, ["AccessViolation", "Jump", "%X" % uBaseAddress], "AV?:%s" % sAddressId));
  
  print "* Starting tests...";
  for oTest in aoTests:
    if bFailed:
      break;
    oTest.fRun();
  for oTest in aoTests:
    oTest.fWait();
  
  if bFailed:
      print "* Tests failed."
      sys.exit(1);
  else:
      print "* All tests passed!"
      sys.exit(0);
