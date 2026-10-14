TIMEOUT(300000, log.testFailed());

var outputPath =
  "/workspace/experiments/cooja/results/"
  + "step6d1b-neighbor-census/"
  + "census-result.json";

var summaries = {};
var entries = {};
var selfLines = {};
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


function finish() {
  if (finished) {
    return;
  }

  finished = true;

  var result = {
    schema_version: 1,
    experiment:
      "RANGER-COOJA-RPL-NEIGHBOR-CENSUS",
    simulation_seed:
      sim.getRandomSeed(),
    summaries:
      summaries,
    entries:
      entries,
    self_lines:
      selfLines,
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
    "RANGER_NEIGHBOR_CENSUS_DONE "
    + "nodes="
    + countKeys(summaries)
    + "\n"
  );

  log.testOK();
}


while (true) {
  YIELD();

  if (
    msg.indexOf(
      "RANGER_NEIGHBOR_SELF node="
    ) >= 0
  ) {
    selfLines[String(id)] = msg;
  }

  if (
    msg.indexOf(
      "RANGER_NEIGHBOR_ENTRY node="
    ) >= 0
  ) {
    var key = String(id);

    if (!entries[key]) {
      entries[key] = [];
    }

    entries[key].push(msg);
  }

  var match = msg.match(
    /RANGER_NEIGHBOR_SUMMARY node=([0-9]+) count=([0-9]+)/
  );

  if (match) {
    var nodeId =
      parseInt(match[1]);

    var count =
      parseInt(match[2]);

    summaries[
      String(nodeId)
    ] = count;

    if (
      countKeys(summaries) === 8
    ) {
      finish();
    }
  }
}
