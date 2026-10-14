TIMEOUT(30000, log.log("RANGER_ASSERT_TIMEOUT\n"); log.testFailed());

var accept2 = false;
var accept3 = false;
var accept4 = false;
var reject5 = false;
var corePass = false;

while (true) {
  YIELD();

  if (msg.indexOf("RANGER_ACCEPT node=2 epoch=1 revoked=5") >= 0) {
    accept2 = true;
  }
  if (msg.indexOf("RANGER_ACCEPT node=3 epoch=1 revoked=5") >= 0) {
    accept3 = true;
  }
  if (msg.indexOf("RANGER_ACCEPT node=4 epoch=1 revoked=5") >= 0) {
    accept4 = true;
  }
  if (msg.indexOf("RANGER_REJECT node=5 epoch=1 revoked=5") >= 0) {
    reject5 = true;
  }
  if (msg.indexOf("RANGER_CORE_PASS epoch=1 accepted=3 rejected=1") >= 0) {
    corePass = true;
  }

  if (accept2 && accept3 && accept4 && reject5 && corePass) {
    log.log("RANGER_ASSERT_PASS accept2=1 accept3=1 accept4=1 reject5=1 core=1\n");
    log.testOK();
  }
}
