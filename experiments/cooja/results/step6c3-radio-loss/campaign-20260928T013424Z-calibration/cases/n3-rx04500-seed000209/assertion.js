TIMEOUT(650000, log.log("RANGER_RADIO_ASSERT_TIMEOUT\n"); log.testFailed());

var outputPath = "/workspace/experiments/cooja/results/step6c3-radio-loss/campaign-20260928T013424Z-calibration/cases/n3-rx04500-seed000209/cooja-result.json";

var expectedN = 3;
var expectedRxSuccess = 0.45;
var expectedSimulationSeed = 209;

var started = false;
var finished = false;

var firstEventTime = -1;
var bootstrapComplete = false;
var bootstrapTime = -1;

var codedAllSent = false;
var codedAllSentTime = -1;

var registeredMask = 0;
var reconstructedMask = 0;
var reportMask = 0;

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

function finishExperiment(trigger) {
  if (finished) {
    return;
  }

  finished = true;

  var registeredCount = maskCount(registeredMask, 2, 8);
  var reconstructedCount = maskCount(reconstructedMask, 2, 7);
  var reportCount = maskCount(reportMask, 2, 8);

  var outcome;

  if (revokedReconstructed) {
    outcome = "SAFETY_FAIL";
  } else if (!bootstrapComplete) {
    outcome = "BOOTSTRAP_FAIL";
  } else if (reconstructedCount === 6) {
    outcome = "REKEY_COMPLETE";
  } else {
    outcome = "REKEY_INCOMPLETE";
  }

  var result = {
    schema_version: 1,
    experiment: "RANGER-COOJA-UDGM-RADIO-LOSS",
    outcome: outcome,
    trigger: trigger,

    expected_k: 3,
    expected_n: expectedN,
    expected_success_ratio_tx: 1.0,
    expected_success_ratio_rx: expectedRxSuccess,
    expected_simulation_seed: expectedSimulationSeed,

    observed_simulation_seed: sim.getRandomSeed(),

    first_event_time: firstEventTime,
    finish_time: sim.getSimulationTime(),

    bootstrap_complete: bootstrapComplete,
    bootstrap_time: bootstrapTime,

    registered_mask: registeredMask,
    registered_count: registeredCount,

    coded_all_sent: codedAllSent,
    coded_all_sent_time: codedAllSentTime,

    authorized_reconstructed_mask: reconstructedMask,
    authorized_reconstructed_count: reconstructedCount,
    authorized_reconstruction_ratio: reconstructedCount / 6.0,

    revoked_reconstructed: revokedReconstructed,
    revoked_reject_observed: revokedRejectObserved,

    report_mask: reportMask,
    report_count: reportCount,

    reconstructed_times: reconstructedTimes,
    fragment_unique_max: fragmentUniqueMax
  };

  log.writeFile(
    outputPath,
    JSON.stringify(result, null, 2) + "\n"
  );

  log.log(
    "RANGER_RADIO_RESULT outcome=" +
    outcome +
    " registered=" +
    registeredCount +
    " reconstructed=" +
    reconstructedCount +
    " revoked_reconstructed=" +
    revokedReconstructed +
    " seed=" +
    sim.getRandomSeed() +
    "\n"
  );

  /*
   * A scientifically valid BOOTSTRAP_FAIL, REKEY_INCOMPLETE or SAFETY_FAIL
   * is still a successfully executed experiment.
   * TEST FAILED is reserved for the harness itself.
   */
  log.testOK();
}

while (true) {
  YIELD();

  if (!started) {
    started = true;
    firstEventTime = time;

    GENERATE_MSG(
      300000,
      "RANGER_SCRIPT_BOOTSTRAP_DEADLINE"
    );
  }

  if (msg === "RANGER_SCRIPT_BOOTSTRAP_DEADLINE") {
    if (!bootstrapComplete) {
      finishExperiment("bootstrap_deadline");
    }
    continue;
  }

  if (msg === "RANGER_SCRIPT_REKEY_DEADLINE") {
    if (bootstrapComplete) {
      finishExperiment("rekey_deadline");
    }
    continue;
  }

  if (msg === "RANGER_SCRIPT_SETTLE_DEADLINE") {
    if (bootstrapComplete && codedAllSent) {
      finishExperiment("post_send_settle");
    }
    continue;
  }

  var reg =
    msg.match(/RANGER_RPL_REGISTER node=([0-9]+) registered=/);

  if (reg) {
    var registeredNode = parseInt(reg[1]);

    if (registeredNode >= 2 && registeredNode <= 8) {
      registeredMask |= (1 << registeredNode);
    }
  }

  if (
    !bootstrapComplete &&
    msg.indexOf("RANGER_CODED_READY registered=7/7") >= 0
  ) {
    bootstrapComplete = true;
    bootstrapTime = time;

    GENERATE_MSG(
      180000,
      "RANGER_SCRIPT_REKEY_DEADLINE"
    );
  }

  var fragment = msg.match(
    /RANGER_CODED_FRAGMENT node=([0-9]+).*unique=([0-9]+)\/([0-9]+)/
  );

  if (fragment) {
    var fragmentNode = parseInt(fragment[1]);
    var uniqueCount = parseInt(fragment[2]);

    if (
      fragmentUniqueMax[fragmentNode] === undefined ||
      uniqueCount > fragmentUniqueMax[fragmentNode]
    ) {
      fragmentUniqueMax[fragmentNode] = uniqueCount;
    }
  }

  var rec =
    msg.match(/RANGER_CODED_RECONSTRUCT node=([0-9]+).*epoch=1/);

  if (rec) {
    var reconstructedNode = parseInt(rec[1]);

    if (reconstructedNode === 8) {
      revokedReconstructed = true;
      finishExperiment("revoked_reconstruction");
      continue;
    }

    if (
      reconstructedNode >= 2 &&
      reconstructedNode <= 7
    ) {
      reconstructedMask |= (1 << reconstructedNode);

      if (reconstructedTimes[reconstructedNode] === undefined) {
        reconstructedTimes[reconstructedNode] = time;
      }
    }
  }

  var reject =
    msg.match(/RANGER_CODED_REJECT node=([0-9]+)/);

  if (reject && parseInt(reject[1]) === 8) {
    revokedRejectObserved = true;
  }

  var report =
    msg.match(/RANGER_RPL_REPORT node=([0-9]+).*reports=/);

  if (report) {
    var reportNode = parseInt(report[1]);

    if (reportNode >= 2 && reportNode <= 8) {
      reportMask |= (1 << reportNode);
    }
  }

  if (
    !codedAllSent &&
    msg.indexOf("RANGER_CODED_ALL_SENT") >= 0
  ) {
    codedAllSent = true;
    codedAllSentTime = time;

    GENERATE_MSG(
      60000,
      "RANGER_SCRIPT_SETTLE_DEADLINE"
    );
  }
}
