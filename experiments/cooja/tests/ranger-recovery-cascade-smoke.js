TIMEOUT(420000, log.testFailed());

var outputPath =
  "/workspace/experiments/cooja/results/"
  + "step6d1d-recovery-cascade-smoke/"
  + "recovery-cascade-result.json";

var initial6 = 0;
var initial7 = 0;

var drops6 = 0;
var drops7 = 0;

var node6Round1Request5 = false;
var node7Round1Request6 = false;
var node7Round2Request6 = false;

var node6RepairFrom5 = false;
var node7RepairFrom6 = false;

var node6Recovered = false;
var node7Recovered = false;

var node6RecoveryRound = 0;
var node7RecoveryRound = 0;

var node6RecoveryTime = -1;
var node7RecoveryTime = -1;

var revokedActivity = false;
var revokedReconstructed = false;

var finishScheduled = false;
var finished = false;


function finish(trigger) {
  if (finished) {
    return;
  }

  finished = true;

  var causalOrder =
    node6RecoveryTime >= 0
    && node7RecoveryTime >= 0
    && node6RecoveryTime
       < node7RecoveryTime;

  var success = (
    initial6 === 2
    && initial7 === 2

    && drops6 === 3
    && drops7 === 3

    && node7Round1Request6
    && node6Round1Request5

    && node6RepairFrom5
    && node6Recovered
    && node6RecoveryRound === 1

    && node7Round2Request6
    && node7RepairFrom6
    && node7Recovered
    && node7RecoveryRound === 2

    && causalOrder

    && !revokedActivity
    && !revokedReconstructed
  );

  var result = {
    schema_version: 1,

    experiment:
      "RANGER-COOJA-RECOVERY-CASCADE-SMOKE",

    trigger: trigger,

    simulation_seed:
      sim.getRandomSeed(),

    initial_unique: {
      "6": initial6,
      "7": initial7
    },

    controlled_drops: {
      "6": drops6,
      "7": drops7
    },

    round1: {
      node7_requested_node6:
        node7Round1Request6,

      node6_requested_node5:
        node6Round1Request5,

      node6_repaired_from_node5:
        node6RepairFrom5,

      node6_recovered:
        node6Recovered,

      node6_recovery_round:
        node6RecoveryRound,

      node6_recovery_time:
        node6RecoveryTime
    },

    round2: {
      node7_requested_node6:
        node7Round2Request6,

      node7_repaired_from_node6:
        node7RepairFrom6,

      node7_recovered:
        node7Recovered,

      node7_recovery_round:
        node7RecoveryRound,

      node7_recovery_time:
        node7RecoveryTime
    },

    causal_order:
      causalOrder,

    revoked_recovery_activity:
      revokedActivity,

    revoked_reconstructed:
      revokedReconstructed,

    success:
      success,

    finish_time:
      sim.getSimulationTime()
  };

  log.writeFile(
    outputPath,
    JSON.stringify(
      result,
      null,
      2
    ) + "\n"
  );

  log.log(
    "RANGER_RECOVERY_CASCADE_RESULT "
    + "success=" + success
    + " node6_round="
    + node6RecoveryRound
    + " node7_round="
    + node7RecoveryRound
    + " causal="
    + causalOrder
    + "\n"
  );

  if (success) {
    log.testOK();
  } else {
    log.testFailed();
  }
}


while (true) {
  YIELD();

  var coded = msg.match(
    /RANGER_CODED_FRAGMENT node=([67]) .*unique=([0-9]+)\/3/
  );

  if (coded) {
    var codedNode =
      parseInt(coded[1]);

    var unique =
      parseInt(coded[2]);

    if (
      codedNode === 6
      && unique > initial6
    ) {
      initial6 = unique;
    }

    if (
      codedNode === 7
      && unique > initial7
    ) {
      initial7 = unique;
    }
  }


  var drop = msg.match(
    /RANGER_RECOVERY_SMOKE_DROP target=([67]) .*fragment=([0-9]+)/
  );

  if (drop) {
    var dropNode =
      parseInt(drop[1]);

    if (dropNode === 6) {
      drops6++;
    }

    if (dropNode === 7) {
      drops7++;
    }
  }


  var request = msg.match(
    /RANGER_RECOVERY_REQUEST node=([0-9]+) neighbor=([0-9]+) round=([0-9]+) /
  );

  if (request) {
    var requester =
      parseInt(request[1]);

    var neighbor =
      parseInt(request[2]);

    var round =
      parseInt(request[3]);

    if (
      requester === 8
      || neighbor === 8
    ) {
      revokedActivity = true;
    }

    if (
      requester === 7
      && neighbor === 6
      && round === 1
    ) {
      node7Round1Request6 = true;
    }

    if (
      requester === 6
      && neighbor === 5
      && round === 1
    ) {
      node6Round1Request5 = true;
    }

    if (
      requester === 7
      && neighbor === 6
      && round === 2
    ) {
      node7Round2Request6 = true;
    }
  }


  var response = msg.match(
    /RANGER_RECOVERY_FRAGMENT_SEND responder=([0-9]+) requester=([0-9]+) .*fragment=([0-9]+)/
  );

  if (response) {
    var responder =
      parseInt(response[1]);

    var requesterId =
      parseInt(response[2]);

    if (
      responder === 8
      || requesterId === 8
    ) {
      revokedActivity = true;
    }

    if (
      responder === 5
      && requesterId === 6
    ) {
      node6RepairFrom5 = true;
    }

    if (
      responder === 6
      && requesterId === 7
    ) {
      node7RepairFrom6 = true;
    }
  }


  var reconstruct = msg.match(
    /RANGER_RECOVERY_RECONSTRUCT node=([0-9]+).*round=([0-9]+)/
  );

  if (reconstruct) {
    var node =
      parseInt(reconstruct[1]);

    var recoveryRound =
      parseInt(reconstruct[2]);

    if (node === 8) {
      revokedReconstructed = true;
    }

    if (node === 6) {
      node6Recovered = true;
      node6RecoveryRound =
        recoveryRound;
      node6RecoveryTime =
        sim.getSimulationTime();
    }

    if (node === 7) {
      node7Recovered = true;
      node7RecoveryRound =
        recoveryRound;
      node7RecoveryTime =
        sim.getSimulationTime();

      if (!finishScheduled) {
        finishScheduled = true;

        GENERATE_MSG(
          10000,
          "RANGER_CASCADE_SETTLE"
        );
      }
    }
  }


  if (
    msg === "RANGER_CASCADE_SETTLE"
  ) {
    finish(
      "post_cascade_settle"
    );
  }
}
