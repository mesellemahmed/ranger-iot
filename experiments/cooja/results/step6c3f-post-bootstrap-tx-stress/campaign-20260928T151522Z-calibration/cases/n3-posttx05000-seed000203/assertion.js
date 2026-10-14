TIMEOUT(650000, log.testFailed());

var outputPath = "/workspace/experiments/cooja/results/step6c3f-post-bootstrap-tx-stress/campaign-20260928T151522Z-calibration/cases/n3-posttx05000-seed000203/cooja-result.json";

var expectedN = 3;
var targetTx = 0.5;
var expectedSeed = 203;

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
  } else if (revokedReconstructed) {
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
      "RANGER-COOJA-POST-BOOTSTRAP-UDGM-TX-STRESS",

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
      "RANGER_CODED_ALL_SENT"
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
