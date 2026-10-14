TIMEOUT(420000, log.testFailed());

var outputPath =
  "/workspace/experiments/cooja/results/"
  + "step6d1c-recovery-core-smoke/"
  + "recovery-core-result.json";

var initialMaxNode4 = 0;
var smokeDrops = 0;

var requestPeers = {};
var responsePeers = {};

var recoveryFragments = 0;
var recoveryFragmentIndexes = {};

var recoveredNode4 = false;
var recoveryRound = 0;

var revokedRecoveryActivity = false;
var revokedReconstructed = false;

var finishScheduled = false;
var finished = false;


function countKeys(object) {
  var count = 0;

  for (var key in object) {
    if (object.hasOwnProperty(key)) {
      count++;
    }
  }

  return count;
}


function finish(trigger) {
  if (finished) {
    return;
  }

  finished = true;

  var requestsExact =
    requestPeers["3"] === true
    && requestPeers["5"] === true
    && countKeys(requestPeers) === 2;

  var responsesExact =
    responsePeers["3"] === true
    && responsePeers["5"] === true
    && countKeys(responsePeers) === 2;

  var fragment2 =
    recoveryFragmentIndexes["2"]
    === true;

  var success = (
    initialMaxNode4 === 2
    && smokeDrops === 3
    && requestsExact
    && responsesExact
    && recoveryFragments >= 1
    && fragment2
    && recoveredNode4
    && recoveryRound === 1
    && !revokedRecoveryActivity
    && !revokedReconstructed
  );

  var result = {
    schema_version: 1,

    experiment:
      "RANGER-COOJA-RECOVERY-CORE-SMOKE",

    trigger: trigger,

    simulation_seed:
      sim.getRandomSeed(),

    target_node: 4,

    initial_unique_before_recovery:
      initialMaxNode4,

    controlled_initial_drops:
      smokeDrops,

    request_peers:
      Object.keys(requestPeers),

    response_peers:
      Object.keys(responsePeers),

    recovery_fragment_count:
      recoveryFragments,

    recovery_fragment_indexes:
      Object.keys(
        recoveryFragmentIndexes
      ),

    recovery_round:
      recoveryRound,

    recovered:
      recoveredNode4,

    revoked_recovery_activity:
      revokedRecoveryActivity,

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
    "RANGER_RECOVERY_CORE_RESULT "
    + "success=" + success
    + " initial=" + initialMaxNode4
    + " drops=" + smokeDrops
    + " requests="
    + countKeys(requestPeers)
    + " responses="
    + countKeys(responsePeers)
    + " round=" + recoveryRound
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

  var initial = msg.match(
    /RANGER_CODED_FRAGMENT node=4 .*unique=([0-9]+)\/3/
  );

  if (initial) {
    var value =
      parseInt(initial[1]);

    if (value > initialMaxNode4) {
      initialMaxNode4 = value;
    }
  }

  var drop = msg.match(
    /RANGER_RECOVERY_SMOKE_DROP target=4 .*fragment=([0-9]+)/
  );

  if (drop) {
    smokeDrops++;
  }

  var request = msg.match(
    /RANGER_RECOVERY_REQUEST node=([0-9]+) neighbor=([0-9]+) round=([0-9]+) .*mask=([0-9]+) needed=([0-9]+)/
  );

  if (request) {
    var requester =
      parseInt(request[1]);

    var peer =
      parseInt(request[2]);

    var round =
      parseInt(request[3]);

    if (
      requester === 8 ||
      peer === 8
    ) {
      revokedRecoveryActivity = true;
    }

    if (requester === 4) {
      requestPeers[
        String(peer)
      ] = true;

      if (round > recoveryRound) {
        recoveryRound = round;
      }
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
      responder === 8 ||
      requesterId === 8
    ) {
      revokedRecoveryActivity = true;
    }

    if (requesterId === 4) {
      responsePeers[
        String(responder)
      ] = true;
    }
  }

  var fragment = msg.match(
    /RANGER_RECOVERY_FRAGMENT node=4 responder=([0-9]+) .*fragment=([0-9]+) unique=([0-9]+)\/3/
  );

  if (fragment) {
    recoveryFragments++;

    recoveryFragmentIndexes[
      String(
        parseInt(fragment[2])
      )
    ] = true;
  }

  var reconstruct = msg.match(
    /RANGER_RECOVERY_RECONSTRUCT node=([0-9]+).*round=([0-9]+)/
  );

  if (reconstruct) {
    var reconstructedNode =
      parseInt(reconstruct[1]);

    var reconstructedRound =
      parseInt(reconstruct[2]);

    if (reconstructedNode === 8) {
      revokedReconstructed = true;
    }

    if (reconstructedNode === 4) {
      recoveredNode4 = true;

      if (
        reconstructedRound >
        recoveryRound
      ) {
        recoveryRound =
          reconstructedRound;
      }

      if (!finishScheduled) {
        finishScheduled = true;

        GENERATE_MSG(
          10000,
          "RANGER_RECOVERY_SETTLE"
        );
      }
    }
  }

  if (
    msg === "RANGER_RECOVERY_SETTLE"
  ) {
    finish(
      "post_recovery_settle"
    );
  }
}
