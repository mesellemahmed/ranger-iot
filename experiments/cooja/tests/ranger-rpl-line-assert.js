TIMEOUT(600000, log.log("RANGER_RPL_ASSERT_TIMEOUT\n"); log.testFailed());

var registered = {};
var accepted = {};
var rejected = {};
var corePass = false;

while (true) {
  YIELD();

  var matchRegister = msg.match(/RANGER_RPL_REGISTER node=([0-9]+) registered=/);
  if (matchRegister) {
    registered[parseInt(matchRegister[1])] = true;
  }

  var matchAccept = msg.match(/RANGER_RPL_ACCEPT node=([0-9]+) epoch=1 revoked=8/);
  if (matchAccept) {
    accepted[parseInt(matchAccept[1])] = true;
  }

  var matchReject = msg.match(/RANGER_RPL_REJECT node=([0-9]+) epoch=1 revoked=8/);
  if (matchReject) {
    rejected[parseInt(matchReject[1])] = true;
  }

  if (msg.indexOf("RANGER_RPL_CORE_PASS epoch=1 registered=7 accepted=6 rejected=1") >= 0) {
    corePass = true;
  }

  var allRegistered =
    registered[2] && registered[3] && registered[4] &&
    registered[5] && registered[6] && registered[7] && registered[8];

  var allAccepted =
    accepted[2] && accepted[3] && accepted[4] &&
    accepted[5] && accepted[6] && accepted[7];

  var revokedRejected = rejected[8];

  if (allRegistered && allAccepted && revokedRejected && corePass) {
    log.log(
      "RANGER_RPL_ASSERT_PASS " +
      "registered=7 accepted=6 rejected=1 farthest_node=8\n"
    );
    log.testOK();
  }
}
