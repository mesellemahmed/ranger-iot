TIMEOUT(650000, log.testFailed());

var outputPath = "/workspace/experiments/cooja/results/step7b3-cooja-topology/20261003T144752/compact-onehop/adaptive-v2/campaign-20261004T171623Z-calibration/cases/n5-posttx02000-seed004518/cooja-result.json";

var expectedN = 5;
var targetTx = 0.2;
var expectedSeed = 4518;

var finished = false;
var started = false;

var registeredMask = 0;
var reconstructedMask = 0;
var reportMask = 0;

var bootstrapComplete = false;
var bootstrapTime = -1;

var switchAttempted = false;
var switchApplied = false;
var switchTime = -1;

var radioClass = null;
var radioTxBefore = null;
var radioTxAfter = null;
var switchError = null;

var firstCodedSendTime = -1;
var codedAllSent = false;
var codedAllSentTime = -1;

var revokedReconstructed = false;
var revokedRejectObserved = false;

var reconstructedTimes = {};

var recoveryEpochPrimeSendCount = 0;
var recoveryEpochPrimeReceiveCount = 0;
var recoveryEpochPrimeBytes = 0;

var recoveryRequestCount = 0;
var recoveryRequestBytes = 0;

var recoveryRoundEventCount = 0;
var recoveryMaxRound = 0;

var recoveryFragmentSendCount = 0;
var recoveryFragmentSendBytes = 0;
var recoveryFragmentReceiveCount = 0;

var recoveryReconstructedMask = 0;
var recoveryReconstructedTimes = {};

var firstRecoveryRequestTime = -1;
var firstRecoveryReconstructTime = -1;
var lastRecoveryReconstructTime = -1;

var revokedRecoveryActivity = false;

/*
 * Adaptive V2 accounting.
 */
var adaptiveInitialAllSent = false;
var adaptiveInitialAllSentTime = -1;

var adaptiveNackArmCount = 0;
var adaptiveNackSourceCount = 0;
var adaptiveNackForwardCount = 0;
var adaptiveNackGmCount = 0;

var adaptiveParityReleaseCount = 0;
var adaptiveParitySendCount = 0;
var adaptiveParityAlreadyReleasedCount = 0;
var adaptiveParityToRevokedCount = 0;

var adaptiveControlBytes = 0;
var adaptiveParityBytes = 0;

var adaptiveMaxRound = 0;

var firstAdaptiveNackTime = -1;
var firstAdaptiveParityReleaseTime = -1;
var lastAdaptiveParityReleaseTime = -1;
var fragmentUniqueMax = {};


function maskCount(mask, firstNode, lastNode) {
  var count = 0;

  for (var nodeId = firstNode; nodeId <= lastNode; nodeId++) {
    if ((mask & (1 << nodeId)) !== 0) {
      count++;
    }
  }

  return count;
}


function writeAndFinish(trigger, infrastructureFailure) {
  if (finished) {
    return;
  }

  finished = true;

  var registeredCount = maskCount(
    registeredMask,
    2,
    8
  );

  var reconstructedCount = maskCount(
    reconstructedMask,
    2,
    7
  );

  var reportCount = maskCount(
    reportMask,
    2,
    8
  );

  var outcome;

  if (infrastructureFailure) {
    outcome = "INFRA_FAIL";
  } else if (
    revokedReconstructed ||
    revokedRecoveryActivity
  ) {
    outcome = "SAFETY_FAIL";
  } else if (!bootstrapComplete) {
    outcome = "BOOTSTRAP_FAIL";
  } else if (reconstructedCount === 6) {
    outcome = "REKEY_COMPLETE";
  } else {
    outcome = "REKEY_INCOMPLETE";
  }

  var switchBeforeFirstSend = null;

  if (
    switchTime >= 0 &&
    firstCodedSendTime >= 0
  ) {
    switchBeforeFirstSend =
      switchTime < firstCodedSendTime;
  }

  var result = {
    schema_version: 1,
    experiment:
      "RANGER-COOJA-ADAPTIVE-V2-POST-BOOTSTRAP-UDGM-TX-STRESS",

    outcome: outcome,
    trigger: trigger,

    expected_k: 3,
    expected_n: expectedN,

    expected_initial_success_ratio_tx: 1.0,
    expected_initial_success_ratio_rx: 1.0,
    target_success_ratio_tx: targetTx,

    expected_simulation_seed: expectedSeed,
    observed_simulation_seed:
      sim.getRandomSeed(),

    bootstrap_complete: bootstrapComplete,
    bootstrap_time: bootstrapTime,

    registered_mask: registeredMask,
    registered_count: registeredCount,

    radio_medium_class: radioClass,
    radio_switch_attempted: switchAttempted,
    radio_switch_applied: switchApplied,
    radio_switch_time: switchTime,
    radio_success_ratio_tx_before: radioTxBefore,
    radio_success_ratio_tx_after: radioTxAfter,
    radio_switch_error: switchError,

    first_coded_send_time: firstCodedSendTime,
    switch_before_first_coded_send:
      switchBeforeFirstSend,

    coded_all_sent: codedAllSent,
    coded_all_sent_time: codedAllSentTime,

    authorized_reconstructed_mask:
      reconstructedMask,
    authorized_reconstructed_count:
      reconstructedCount,
    authorized_reconstruction_ratio:
      reconstructedCount / 6.0,

    revoked_reconstructed:
      revokedReconstructed,
    revoked_reject_observed:
      revokedRejectObserved,

    report_mask: reportMask,
    report_count: reportCount,

    recovery_epoch_prime_send_count:
      recoveryEpochPrimeSendCount,

    recovery_epoch_prime_receive_count:
      recoveryEpochPrimeReceiveCount,

    recovery_epoch_prime_bytes:
      recoveryEpochPrimeBytes,

    recovery_request_count:
      recoveryRequestCount,

    recovery_request_bytes:
      recoveryRequestBytes,

    recovery_round_event_count:
      recoveryRoundEventCount,

    recovery_max_round:
      recoveryMaxRound,

    recovery_fragment_send_count:
      recoveryFragmentSendCount,

    recovery_fragment_send_bytes:
      recoveryFragmentSendBytes,

    recovery_fragment_receive_count:
      recoveryFragmentReceiveCount,

    recovery_reconstructed_mask:
      recoveryReconstructedMask,

    recovery_reconstructed_count:
      maskCount(
        recoveryReconstructedMask,
        2,
        7
      ),

    recovery_reconstructed_times:
      recoveryReconstructedTimes,

    first_recovery_request_time:
      firstRecoveryRequestTime,

    first_recovery_reconstruct_time:
      firstRecoveryReconstructTime,

    last_recovery_reconstruct_time:
      lastRecoveryReconstructTime,

    revoked_recovery_activity:
      revokedRecoveryActivity,

    adaptive_initial_all_sent:
      adaptiveInitialAllSent,

    adaptive_initial_all_sent_time:
      adaptiveInitialAllSentTime,

    adaptive_nack_arm_count:
      adaptiveNackArmCount,

    adaptive_nack_source_count:
      adaptiveNackSourceCount,

    adaptive_nack_forward_count:
      adaptiveNackForwardCount,

    adaptive_nack_gm_count:
      adaptiveNackGmCount,

    adaptive_parity_release_count:
      adaptiveParityReleaseCount,

    adaptive_parity_send_count:
      adaptiveParitySendCount,

    adaptive_parity_already_released_count:
      adaptiveParityAlreadyReleasedCount,

    adaptive_parity_to_revoked_count:
      adaptiveParityToRevokedCount,

    adaptive_control_bytes:
      adaptiveControlBytes,

    adaptive_parity_bytes:
      adaptiveParityBytes,

    adaptive_overhead_bytes:
      adaptiveControlBytes
      + adaptiveParityBytes,

    adaptive_max_round:
      adaptiveMaxRound,

    first_adaptive_nack_time:
      firstAdaptiveNackTime,

    first_adaptive_parity_release_time:
      firstAdaptiveParityReleaseTime,

    last_adaptive_parity_release_time:
      lastAdaptiveParityReleaseTime,

    reconstructed_times:
      reconstructedTimes,
    fragment_unique_max:
      fragmentUniqueMax,

    finish_time:
      sim.getSimulationTime()
  };

  log.writeFile(
    outputPath,
    JSON.stringify(result, null, 2) + "\n"
  );

  log.log(
    "RANGER_POST_BOOTSTRAP_RESULT " +
    "outcome=" + outcome +
    " target_tx=" + targetTx +
    " registered=" + registeredCount +
    " reconstructed=" + reconstructedCount +
    " switch=" + switchApplied +
    " seed=" + sim.getRandomSeed() +
    "\n"
  );

  if (infrastructureFailure) {
    log.testFailed();
  } else {
    log.testOK();
  }
}


function applyRadioStress() {
  if (switchAttempted) {
    return;
  }

  switchAttempted = true;
  switchTime = time;

  try {
    var radioMedium = sim.getRadioMedium();

    radioClass = String(
      radioMedium.getClass().getName()
    );

    radioTxBefore = Number(
      radioMedium.SUCCESS_RATIO_TX
    );

    radioMedium.SUCCESS_RATIO_TX =
      targetTx;

    radioTxAfter = Number(
      radioMedium.SUCCESS_RATIO_TX
    );

    switchApplied =
      Math.abs(radioTxAfter - targetTx) < 1e-12;

    log.log(
      "RANGER_POST_BOOTSTRAP_SWITCH " +
      "class=" + radioClass +
      " before=" + radioTxBefore +
      " target=" + targetTx +
      " after=" + radioTxAfter +
      " time=" + switchTime +
      "\n"
    );

    if (!switchApplied) {
      switchError =
        "radio_success_ratio_tx_readback_mismatch";

      writeAndFinish(
        "radio_switch_mismatch",
        true
      );
    }

  } catch (error) {
    switchError = String(error);

    writeAndFinish(
      "radio_switch_exception",
      true
    );
  }
}


while (true) {
  YIELD();

  if (!started) {
    started = true;

    GENERATE_MSG(
      300000,
      "RANGER_SCRIPT_BOOTSTRAP_DEADLINE"
    );
  }

  if (
    msg ===
    "RANGER_SCRIPT_BOOTSTRAP_DEADLINE"
  ) {
    if (!bootstrapComplete) {
      writeAndFinish(
        "bootstrap_deadline",
        false
      );
    }

    continue;
  }

  if (
    msg ===
    "RANGER_SCRIPT_REKEY_DEADLINE"
  ) {
    if (bootstrapComplete) {
      writeAndFinish(
        "rekey_deadline",
        false
      );
    }

    continue;
  }

  if (
    msg ===
    "RANGER_SCRIPT_SETTLE_DEADLINE"
  ) {
    if (
      bootstrapComplete &&
      codedAllSent
    ) {
      writeAndFinish(
        "post_send_settle",
        false
      );
    }

    continue;
  }

  var reg = msg.match(
    /RANGER_RPL_REGISTER node=([0-9]+) registered=/
  );

  if (reg) {
    var registeredNode =
      parseInt(reg[1]);

    if (
      registeredNode >= 2 &&
      registeredNode <= 8
    ) {
      registeredMask |=
        (1 << registeredNode);
    }
  }

  if (
    !bootstrapComplete &&
    msg.indexOf(
      "RANGER_CODED_READY registered=7/7"
    ) >= 0
  ) {
    bootstrapComplete = true;
    bootstrapTime = time;

    applyRadioStress();

    if (finished) {
      continue;
    }

    GENERATE_MSG(
      180000,
      "RANGER_SCRIPT_REKEY_DEADLINE"
    );
  }

  if (
    firstCodedSendTime < 0 &&
    msg.indexOf(
      "RANGER_CODED_SEND target="
    ) >= 0
  ) {
    firstCodedSendTime = time;
  }

  var fragment = msg.match(
    /RANGER_CODED_FRAGMENT node=([0-9]+).*unique=([0-9]+)\/([0-9]+)/
  );

  if (fragment) {
    var fragmentNode =
      parseInt(fragment[1]);

    var uniqueCount =
      parseInt(fragment[2]);

    if (
      fragmentUniqueMax[fragmentNode]
        === undefined ||
      uniqueCount >
        fragmentUniqueMax[fragmentNode]
    ) {
      fragmentUniqueMax[fragmentNode] =
        uniqueCount;
    }
  }

  var rec = msg.match(
    /RANGER_CODED_RECONSTRUCT node=([0-9]+).*epoch=1/
  );

  if (rec) {
    var reconstructedNode =
      parseInt(rec[1]);

    if (reconstructedNode === 8) {
      revokedReconstructed = true;

      writeAndFinish(
        "revoked_reconstruction",
        false
      );

      continue;
    }

    if (
      reconstructedNode >= 2 &&
      reconstructedNode <= 7
    ) {
      reconstructedMask |=
        (1 << reconstructedNode);

      if (
        reconstructedTimes[
          reconstructedNode
        ] === undefined
      ) {
        reconstructedTimes[
          reconstructedNode
        ] = time;
      }
    }
  }



  if (
    msg.indexOf(
      "RANGER_RECOVERY_EPOCH_SEND "
    ) >= 0
  ) {
    recoveryEpochPrimeSendCount++;
    recoveryEpochPrimeBytes += 6;
  }

  if (
    msg.indexOf(
      "RANGER_RECOVERY_EPOCH node="
    ) >= 0
  ) {
    recoveryEpochPrimeReceiveCount++;
  }



  if (
    msg.indexOf(
      "RANGER_ADAPTIVE_INITIAL_ALL_SENT "
    ) >= 0
  ) {
    adaptiveInitialAllSent = true;
    adaptiveInitialAllSentTime = time;
  }


  if (
    msg.indexOf(
      "RANGER_ADAPTIVE_NACK_ARM "
    ) >= 0
  ) {
    adaptiveNackArmCount++;
  }


  if (
    msg.indexOf(
      "RANGER_ADAPTIVE_NACK_SOURCE "
    ) >= 0
  ) {
    adaptiveNackSourceCount++;
    adaptiveControlBytes += 16;

    if (
      firstAdaptiveNackTime < 0
    ) {
      firstAdaptiveNackTime = time;
    }

    var sourceRound =
      msg.match(
        /round=([0-9]+)/
      );

    if (sourceRound) {
      var sourceRoundValue =
        parseInt(sourceRound[1]);

      if (
        sourceRoundValue >
        adaptiveMaxRound
      ) {
        adaptiveMaxRound =
          sourceRoundValue;
      }
    }
  }


  if (
    msg.indexOf(
      "RANGER_ADAPTIVE_NACK_FORWARD "
    ) >= 0
  ) {
    adaptiveNackForwardCount++;
    adaptiveControlBytes += 16;

    var forwardRound =
      msg.match(
        /round=([0-9]+)/
      );

    if (forwardRound) {
      var forwardRoundValue =
        parseInt(forwardRound[1]);

      if (
        forwardRoundValue >
        adaptiveMaxRound
      ) {
        adaptiveMaxRound =
          forwardRoundValue;
      }
    }
  }


  if (
    msg.indexOf(
      "RANGER_ADAPTIVE_NACK_GM "
    ) >= 0
  ) {
    adaptiveNackGmCount++;

    var gmRound =
      msg.match(
        /round=([0-9]+)/
      );

    if (gmRound) {
      var gmRoundValue =
        parseInt(gmRound[1]);

      if (
        gmRoundValue >
        adaptiveMaxRound
      ) {
        adaptiveMaxRound =
          gmRoundValue;
      }
    }
  }


  if (
    msg.indexOf(
      "RANGER_ADAPTIVE_PARITY_RELEASE "
    ) >= 0
  ) {
    adaptiveParityReleaseCount++;

    if (
      firstAdaptiveParityReleaseTime < 0
    ) {
      firstAdaptiveParityReleaseTime =
        time;
    }

    lastAdaptiveParityReleaseTime =
      time;

    var releaseRound =
      msg.match(
        /round=([0-9]+)/
      );

    if (releaseRound) {
      var releaseRoundValue =
        parseInt(releaseRound[1]);

      if (
        releaseRoundValue >
        adaptiveMaxRound
      ) {
        adaptiveMaxRound =
          releaseRoundValue;
      }
    }
  }


  if (
    msg.indexOf(
      "RANGER_ADAPTIVE_PARITY_ALREADY_RELEASED "
    ) >= 0
  ) {
    adaptiveParityAlreadyReleasedCount++;
  }


  if (
    msg.indexOf(
      "RANGER_ADAPTIVE_PARITY_SEND "
    ) >= 0
  ) {
    adaptiveParitySendCount++;
    adaptiveParityBytes += 9;

    var parityTarget =
      msg.match(
        /target=([0-9]+)/
      );

    if (
      parityTarget &&
      parseInt(
        parityTarget[1]
      ) === 8
    ) {
      adaptiveParityToRevokedCount++;
    }
  }


  var recoveryRequest = msg.match(
    /RANGER_RECOVERY_REQUEST node=([0-9]+) neighbor=([0-9]+) round=([0-9]+).*bytes=([0-9]+)/
  );

  if (recoveryRequest) {
    var recoveryRequester =
      parseInt(recoveryRequest[1]);

    var recoveryNeighbor =
      parseInt(recoveryRequest[2]);

    var requestRound =
      parseInt(recoveryRequest[3]);

    var requestBytes =
      parseInt(recoveryRequest[4]);

    recoveryRequestCount++;
    recoveryRequestBytes +=
      requestBytes;

    if (
      firstRecoveryRequestTime < 0
    ) {
      firstRecoveryRequestTime =
        time;
    }

    if (
      requestRound >
      recoveryMaxRound
    ) {
      recoveryMaxRound =
        requestRound;
    }

    if (
      recoveryRequester === 8 ||
      recoveryNeighbor === 8
    ) {
      revokedRecoveryActivity =
        true;
    }
  }


  var recoveryRound = msg.match(
    /RANGER_RECOVERY_ROUND node=([0-9]+) round=([0-9]+).*requests=([0-9]+)/
  );

  if (recoveryRound) {
    var observedRound =
      parseInt(recoveryRound[2]);

    recoveryRoundEventCount++;

    if (
      observedRound >
      recoveryMaxRound
    ) {
      recoveryMaxRound =
        observedRound;
    }
  }


  var recoverySend = msg.match(
    /RANGER_RECOVERY_FRAGMENT_SEND responder=([0-9]+) requester=([0-9]+).*fragment=([0-9]+)/
  );

  if (recoverySend) {
    var recoveryResponder =
      parseInt(recoverySend[1]);

    var recoveryTarget =
      parseInt(recoverySend[2]);

    recoveryFragmentSendCount++;
    recoveryFragmentSendBytes += 9;

    if (
      recoveryResponder === 8 ||
      recoveryTarget === 8
    ) {
      revokedRecoveryActivity =
        true;
    }
  }


  var recoveryFragment = msg.match(
    /RANGER_RECOVERY_FRAGMENT node=([0-9]+) responder=([0-9]+).*fragment=([0-9]+).*unique=([0-9]+)\/([0-9]+)/
  );

  if (recoveryFragment) {
    var recoveryFragmentNode =
      parseInt(recoveryFragment[1]);

    var recoveryFragmentResponder =
      parseInt(recoveryFragment[2]);

    recoveryFragmentReceiveCount++;

    if (
      recoveryFragmentNode === 8 ||
      recoveryFragmentResponder === 8
    ) {
      revokedRecoveryActivity =
        true;
    }
  }


  var recoveryRec = msg.match(
    /RANGER_RECOVERY_RECONSTRUCT node=([0-9]+).*round=([0-9]+)/
  );

  if (recoveryRec) {
    var recoveryNode =
      parseInt(recoveryRec[1]);

    var recoveryNodeRound =
      parseInt(recoveryRec[2]);

    if (
      recoveryNodeRound >
      recoveryMaxRound
    ) {
      recoveryMaxRound =
        recoveryNodeRound;
    }

    if (recoveryNode === 8) {
      revokedReconstructed = true;
      revokedRecoveryActivity = true;

      writeAndFinish(
        "revoked_recovery_reconstruction",
        false
      );

      continue;
    }

    if (
      recoveryNode >= 2 &&
      recoveryNode <= 7
    ) {
      reconstructedMask |=
        (1 << recoveryNode);

      recoveryReconstructedMask |=
        (1 << recoveryNode);

      if (
        reconstructedTimes[
          recoveryNode
        ] === undefined
      ) {
        reconstructedTimes[
          recoveryNode
        ] = time;
      }

      if (
        recoveryReconstructedTimes[
          recoveryNode
        ] === undefined
      ) {
        recoveryReconstructedTimes[
          recoveryNode
        ] = time;
      }

      if (
        firstRecoveryReconstructTime < 0
      ) {
        firstRecoveryReconstructTime =
          time;
      }

      lastRecoveryReconstructTime =
        time;
    }
  }


  var reject = msg.match(
    /RANGER_CODED_REJECT node=([0-9]+)/
  );

  if (
    reject &&
    parseInt(reject[1]) === 8
  ) {
    revokedRejectObserved = true;
  }

  var report = msg.match(
    /RANGER_RPL_REPORT node=([0-9]+).*reports=/
  );

  if (report) {
    var reportNode =
      parseInt(report[1]);

    if (
      reportNode >= 2 &&
      reportNode <= 8
    ) {
      reportMask |=
        (1 << reportNode);
    }
  }

  if (
    !codedAllSent &&
    msg.indexOf(
      "RANGER_ADAPTIVE_INITIAL_ALL_SENT"
    ) >= 0
  ) {
    codedAllSent = true;
    codedAllSentTime = time;

    GENERATE_MSG(
      60000,
      "RANGER_SCRIPT_SETTLE_DEADLINE"
    );
  }
}
