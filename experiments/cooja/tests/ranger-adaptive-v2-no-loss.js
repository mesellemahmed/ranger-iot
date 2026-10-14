TIMEOUT(420000, log.testFailed());

var outputPath =
  "/workspace/experiments/cooja/results/"
  + "step6e1b-adaptive-v2-no-loss/"
  + "no-loss-result.json";

var expectedAuthorizedMask = 0;

for (var n = 2; n <= 7; n++) {
  expectedAuthorizedMask |=
    (1 << n);
}

var reconstructedMask = 0;

var initialSendCount = 0;

var perTargetSendCount = {
  "2": 0,
  "3": 0,
  "4": 0,
  "5": 0,
  "6": 0,
  "7": 0,
  "8": 0
};

var perTargetFragmentMask = {
  "2": 0,
  "3": 0,
  "4": 0,
  "5": 0,
  "6": 0,
  "7": 0,
  "8": 0
};

var initialAllSent = false;

var recoveryRequestCount = 0;
var recoveryFragmentSendCount = 0;
var recoveryReconstructCount = 0;

var nackCount = 0;

var revokedReconstructed = false;

var finishScheduled = false;
var finished = false;


function bitCount(value) {
  var count = 0;

  while (value !== 0) {
    count += value & 1;
    value >>>= 1;
  }

  return count;
}


function finish(trigger) {
  if (finished) {
    return;
  }

  finished = true;

  var authorizedComplete =
    (
      reconstructedMask
      & expectedAuthorizedMask
    ) === expectedAuthorizedMask;

  var exactPerTarget = true;
  var exactFragments = true;

  for (
    var node = 2;
    node <= 7;
    node++
  ) {
    if (
      perTargetSendCount[
        String(node)
      ] !== 3
    ) {
      exactPerTarget = false;
    }

    /*
     * Initial fragments must be exactly
     * indexes {0,1,2}.
     */
    if (
      perTargetFragmentMask[
        String(node)
      ] !== 7
    ) {
      exactFragments = false;
    }
  }

  var success = (
    initialAllSent
    && initialSendCount === 18
    && exactPerTarget
    && exactFragments
    && perTargetSendCount["8"] === 0
    && authorizedComplete
    && bitCount(
         reconstructedMask
         & expectedAuthorizedMask
       ) === 6
    && !revokedReconstructed
    && recoveryRequestCount === 0
    && recoveryFragmentSendCount === 0
    && recoveryReconstructCount === 0
    && nackCount === 0
  );

  var result = {
    schema_version: 1,

    experiment:
      "RANGER-COOJA-ADAPTIVE-V2-INITIAL-K-NO-LOSS",

    simulation_seed:
      sim.getRandomSeed(),

    trigger:
      trigger,

    initial_send_count:
      initialSendCount,

    expected_initial_send_count:
      18,

    per_target_send_count:
      perTargetSendCount,

    per_target_fragment_mask:
      perTargetFragmentMask,

    initial_all_sent:
      initialAllSent,

    authorized_reconstructed_mask:
      reconstructedMask
      & expectedAuthorizedMask,

    authorized_reconstructed_count:
      bitCount(
        reconstructedMask
        & expectedAuthorizedMask
      ),

    revoked_reconstructed:
      revokedReconstructed,

    recovery_request_count:
      recoveryRequestCount,

    recovery_fragment_send_count:
      recoveryFragmentSendCount,

    recovery_reconstruct_count:
      recoveryReconstructCount,

    nack_count:
      nackCount,

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
    "RANGER_ADAPTIVE_V2_NO_LOSS_RESULT "
    + "success=" + success
    + " sends=" + initialSendCount
    + " reconstructed="
    + result.authorized_reconstructed_count
    + " recovery_requests="
    + recoveryRequestCount
    + " nack="
    + nackCount
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

  var send = msg.match(
    /RANGER_CODED_SEND target=([0-9]+).*fragment=([0-9]+)/
  );

  if (send) {
    var target =
      parseInt(send[1]);

    var fragment =
      parseInt(send[2]);

    initialSendCount++;

    if (
      perTargetSendCount[
        String(target)
      ] !== undefined
    ) {
      perTargetSendCount[
        String(target)
      ]++;

      perTargetFragmentMask[
        String(target)
      ] |=
        (1 << fragment);
    }
  }


  var reconstruct = msg.match(
    /RANGER_CODED_RECONSTRUCT node=([0-9]+)/
  );

  if (reconstruct) {
    var reconstructedNode =
      parseInt(reconstruct[1]);

    if (
      reconstructedNode >= 2 &&
      reconstructedNode <= 7
    ) {
      reconstructedMask |=
        (1 << reconstructedNode);
    }

    if (reconstructedNode === 8) {
      revokedReconstructed = true;
    }
  }


  if (
    msg.indexOf(
      "RANGER_RECOVERY_REQUEST "
    ) >= 0
  ) {
    recoveryRequestCount++;
  }


  if (
    msg.indexOf(
      "RANGER_RECOVERY_FRAGMENT_SEND "
    ) >= 0
  ) {
    recoveryFragmentSendCount++;
  }


  if (
    msg.indexOf(
      "RANGER_RECOVERY_RECONSTRUCT "
    ) >= 0
  ) {
    recoveryReconstructCount++;
  }


  if (
    msg.indexOf(
      "RANGER_ADAPTIVE_NACK_SOURCE "
    ) >= 0
  ) {
    nackCount++;
  }


  if (
    !initialAllSent &&
    msg.indexOf(
      "RANGER_ADAPTIVE_INITIAL_ALL_SENT"
    ) >= 0
  ) {
    initialAllSent = true;

    if (!finishScheduled) {
      finishScheduled = true;

      GENERATE_MSG(
        30000,
        "RANGER_ADAPTIVE_SETTLE"
      );
    }
  }


  if (
    msg ===
    "RANGER_ADAPTIVE_SETTLE"
  ) {
    finish(
      "post_initial_settle"
    );
  }
}
