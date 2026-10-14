TIMEOUT(420000, log.testFailed());

var outputPath =
  "/workspace/experiments/cooja/results/"
  + "step6e1e1-adaptive-v2-nack-parity-smoke/"
  + "nack-parity-result.json";

var sources = {};
var forwards = {};
var gms = {};

var releaseCount = 0;
var releasedRequester = -1;
var releasedRound = -1;
var releasedEpoch = -1;
var releasedFragment = -1;

var releaseTime = -1;
var firstParitySendTime = -1;
var paritySendCount = 0;

var alreadyReleasedCount = 0;

var repairedRequester = false;
var requesterReconstructTime = -1;

var revokedReconstructed = false;
var recoveryReconstructedMask = 0;

var initialAllSent = false;

var finishScheduled = false;
var finished = false;


function keyOf(requester, round) {
  return String(requester)
    + ":"
    + String(round);
}


function finish(trigger) {
  if (finished) {
    return;
  }

  finished = true;

  var key =
    keyOf(
      releasedRequester,
      releasedRound
    );

  var source =
    sources[key];

  var gm =
    gms[key];

  var forwardCount =
    forwards[key] || 0;

  var sourceExists =
    source !== undefined;

  var gmExists =
    gm !== undefined;

  var forwardingNeeded =
    sourceExists
    && source.parent !== 1;

  var forwardingOK =
    !forwardingNeeded
    || forwardCount > 0;

  var causal =
    sourceExists
    && gmExists
    && source.time >= 0
    && gm.time >= source.time
    && releaseTime >= gm.time
    && firstParitySendTime >= releaseTime
    && requesterReconstructTime
       >= firstParitySendTime;

  var requesterWasRecovered =
    releasedRequester >= 0
    && (
      recoveryReconstructedMask
      & (1 << releasedRequester)
    ) !== 0;

  var success = (
    initialAllSent

    && releasedRequester >= 2
    && releasedRequester <= 7

    && releasedRound === 1

    && releasedFragment === 3

    && sourceExists

    && source.unique < 3

    && gmExists

    && forwardingOK

    && releaseCount === 1

    && paritySendCount >= 6

    && repairedRequester

    && causal

    && !requesterWasRecovered

    && !revokedReconstructed
  );

  var result = {
    schema_version: 1,

    experiment:
      "RANGER-COOJA-ADAPTIVE-V2-NACK-PARITY-SMOKE",

    simulation_seed:
      sim.getRandomSeed(),

    trigger:
      trigger,

    initial_all_sent:
      initialAllSent,

    released_requester:
      releasedRequester,

    released_round:
      releasedRound,

    released_epoch:
      releasedEpoch,

    released_fragment:
      releasedFragment,

    source:
      source || null,

    forward_count:
      forwardCount,

    forwarding_needed:
      forwardingNeeded,

    forwarding_ok:
      forwardingOK,

    gm:
      gm || null,

    release_count:
      releaseCount,

    parity_send_count:
      paritySendCount,

    parity_already_released_count:
      alreadyReleasedCount,

    repaired_requester:
      repairedRequester,

    requester_reconstruct_time:
      requesterReconstructTime,

    recovery_reconstructed_requester:
      requesterWasRecovered,

    revoked_reconstructed:
      revokedReconstructed,

    causal_order:
      causal,

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
    "RANGER_V2_NACK_PARITY_RESULT "
    + "success=" + success
    + " requester="
    + releasedRequester
    + " round="
    + releasedRound
    + " fragment="
    + releasedFragment
    + " forwards="
    + forwardCount
    + " sends="
    + paritySendCount
    + " repaired="
    + repairedRequester
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


  if (
    msg.indexOf(
      "RANGER_ADAPTIVE_INITIAL_ALL_SENT"
    ) >= 0
  ) {
    initialAllSent = true;
  }


  var source = msg.match(
    /RANGER_ADAPTIVE_NACK_SOURCE requester=([0-9]+) parent=([0-9]+) round=([0-9]+) epoch=([0-9]+) unique=([0-9]+) bytes=([0-9]+)/
  );

  if (source) {
    var sourceRequester =
      parseInt(source[1]);

    var sourceParent =
      parseInt(source[2]);

    var sourceRound =
      parseInt(source[3]);

    var sourceEpoch =
      parseInt(source[4]);

    var sourceUnique =
      parseInt(source[5]);

    var sourceBytes =
      parseInt(source[6]);

    var sourceKey =
      keyOf(
        sourceRequester,
        sourceRound
      );

    if (
      sources[sourceKey]
      === undefined
    ) {
      sources[sourceKey] = {
        requester:
          sourceRequester,

        parent:
          sourceParent,

        round:
          sourceRound,

        epoch:
          sourceEpoch,

        unique:
          sourceUnique,

        bytes:
          sourceBytes,

        time:
          time
      };
    }
  }


  var forward = msg.match(
    /RANGER_ADAPTIVE_NACK_FORWARD relay=[0-9]+ requester=([0-9]+) parent=[0-9]+ round=([0-9]+) epoch=[0-9]+/
  );

  if (forward) {
    var forwardKey =
      keyOf(
        parseInt(forward[1]),
        parseInt(forward[2])
      );

    forwards[forwardKey] =
      (forwards[forwardKey] || 0)
      + 1;
  }


  var gm = msg.match(
    /RANGER_ADAPTIVE_NACK_GM requester=([0-9]+) via=([0-9]+) round=([0-9]+) epoch=([0-9]+) unique=([0-9]+)/
  );

  if (gm) {
    var gmRequester =
      parseInt(gm[1]);

    var gmRound =
      parseInt(gm[3]);

    var gmKey =
      keyOf(
        gmRequester,
        gmRound
      );

    if (
      gms[gmKey]
      === undefined
    ) {
      gms[gmKey] = {
        requester:
          gmRequester,

        via:
          parseInt(gm[2]),

        round:
          gmRound,

        epoch:
          parseInt(gm[4]),

        unique:
          parseInt(gm[5]),

        time:
          time
      };
    }
  }


  var release = msg.match(
    /RANGER_ADAPTIVE_PARITY_RELEASE requester=([0-9]+) round=([0-9]+) epoch=([0-9]+) fragment=([0-9]+)/
  );

  if (release) {
    releaseCount++;

    if (releasedRequester < 0) {
      releasedRequester =
        parseInt(release[1]);

      releasedRound =
        parseInt(release[2]);

      releasedEpoch =
        parseInt(release[3]);

      releasedFragment =
        parseInt(release[4]);

      releaseTime =
        time;
    }
  }


  if (
    msg.indexOf(
      "RANGER_ADAPTIVE_PARITY_ALREADY_RELEASED"
    ) >= 0
  ) {
    alreadyReleasedCount++;
  }


  var paritySend = msg.match(
    /RANGER_ADAPTIVE_PARITY_SEND target=([0-9]+) requester=([0-9]+) round=([0-9]+) epoch=([0-9]+) fragment=([0-9]+)/
  );

  if (paritySend) {
    var sendRequester =
      parseInt(paritySend[2]);

    var sendRound =
      parseInt(paritySend[3]);

    if (
      sendRequester ===
        releasedRequester
      && sendRound ===
        releasedRound
    ) {
      paritySendCount++;

      if (
        firstParitySendTime < 0
      ) {
        firstParitySendTime =
          time;
      }
    }
  }


  var codedReconstruct = msg.match(
    /RANGER_CODED_RECONSTRUCT node=([0-9]+)/
  );

  if (codedReconstruct) {
    var codedNode =
      parseInt(
        codedReconstruct[1]
      );

    if (codedNode === 8) {
      revokedReconstructed = true;
    }

    if (
      codedNode ===
        releasedRequester
      && releaseTime >= 0
      && time >= releaseTime
    ) {
      repairedRequester = true;

      requesterReconstructTime =
        time;

      if (!finishScheduled) {
        finishScheduled = true;

        GENERATE_MSG(
          10000,
          "RANGER_ADAPTIVE_PARITY_SETTLE"
        );
      }
    }
  }


  var recoveryReconstruct = msg.match(
    /RANGER_RECOVERY_RECONSTRUCT node=([0-9]+)/
  );

  if (recoveryReconstruct) {
    var recoveryNode =
      parseInt(
        recoveryReconstruct[1]
      );

    if (recoveryNode === 8) {
      revokedReconstructed = true;
    }

    if (
      recoveryNode >= 0
      && recoveryNode < 16
    ) {
      recoveryReconstructedMask |=
        (1 << recoveryNode);
    }
  }


  if (
    msg ===
    "RANGER_ADAPTIVE_PARITY_SETTLE"
  ) {
    finish(
      "post_parity_reconstruction"
    );
  }
}
