TIMEOUT(600000, log.log("RANGER_RS_WIRE_ASSERT_TIMEOUT\n"); log.testFailed());

var mode = -1;

var registered = {};

var sends = [];

var receives = [];

var reconstructed = {};

var reconstructMask = {};

var rejected = false;

var belowK = false;

var belowMask = -1;

var maskPass = false;

var corePass = false;

var allShardsSent = false;

var finished = false;


function bitCount(value) {
  var count = 0;

  while (value !== 0) {
    count += value & 1;
    value = value >>> 1;
  }

  return count;
}


function objectCount(obj) {
  var count = 0;

  for (var key in obj) {
    if (
      Object.prototype.hasOwnProperty.call(
        obj,
        key
      )
    ) {
      count++;
    }
  }

  return count;
}


function finishIfReady() {
  if (
    finished ||
    mode < 0 ||
    !corePass ||
    !allShardsSent
  ) {
    return;
  }


  var allRegistered =
    registered[2] &&
    registered[3] &&
    registered[4] &&
    registered[5] &&
    registered[6] &&
    registered[7] &&
    registered[8];


  if (!allRegistered) {
    return;
  }


  var success = false;


  if (mode === 0) {
    var allReconstructed =
      reconstructed[2] &&
      reconstructed[3] &&
      reconstructed[4] &&
      reconstructed[5] &&
      reconstructed[6] &&
      reconstructed[7];


    var masksValid = true;


    for (
      var node = 2;
      node <= 7;
      node++
    ) {
      if (
        bitCount(
          reconstructMask[
            String(node)
          ]
        ) !== 3
      ) {
        masksValid = false;
      }
    }


    success =
      allReconstructed &&
      !reconstructed[8] &&
      rejected &&
      !belowK &&
      maskPass &&
      sends.length === 35 &&
      receives.length === 19 &&
      masksValid;
  }


  if (mode === 1) {
    var controlledMasks =
      reconstructMask["2"] === 7 &&
      reconstructMask["3"] === 11 &&
      reconstructMask["4"] === 19 &&
      reconstructMask["5"] === 13 &&
      reconstructMask["6"] === 26;


    success =
      reconstructed[2] &&
      reconstructed[3] &&
      reconstructed[4] &&
      reconstructed[5] &&
      reconstructed[6] &&
      !reconstructed[7] &&
      !reconstructed[8] &&
      rejected &&
      belowK &&
      belowMask === 3 &&
      maskPass &&
      sends.length === 18 &&
      receives.length === 18 &&
      controlledMasks;
  }


  finished = true;


  var evidence = {
    schema_version: 2,

    experiment:
      "RANGER-COOJA-REAL-RS-WIRE",

    mode:
      mode,

    simulation_seed:
      sim.getRandomSeed(),

    finish_time:
      sim.getSimulationTime(),

    registered_count:
      objectCount(
        registered
      ),

    sends:
      sends,

    receives:
      receives,

    reconstructed:
      reconstructed,

    reconstruct_mask:
      reconstructMask,

    rejected:
      rejected,

    below_k:
      belowK,

    below_mask:
      belowMask,

    mask_pass:
      maskPass,

    core_pass:
      corePass,

    all_shards_sent:
      allShardsSent,

    success:
      success
  };


  var outputPath =
    "/workspace/"
    + "artifacts/article-evidence/"
    + "23-step7c3-cooja-real-rs-wire/"
    + (
      mode === 0
      ? "script-evidence-mode0.json"
      : "script-evidence-mode1.json"
    );


  log.writeFile(
    outputPath,
    JSON.stringify(
      evidence,
      null,
      2
    ) + "\n"
  );


  log.log(
    "RANGER_RS_WIRE_STRUCTURED_RESULT "
    + "mode=" + mode
    + " success=" + success
    + " sends=" + sends.length
    + " receives=" + receives.length
    + " reconstructed="
    + objectCount(reconstructed)
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


  var modeMatch = msg.match(
    /RANGER_RS_WIRE_MODE mode=([01]) payload=16 shard=6 packet=18 k=3 n=5/
  );


  if (modeMatch) {
    mode =
      parseInt(
        modeMatch[1]
      );
  }


  var reg = msg.match(
    /RANGER_RS_WIRE_REGISTER node=([0-9]+) registered=/
  );


  if (reg) {
    registered[
      String(
        parseInt(
          reg[1]
        )
      )
    ] = true;
  }


  var send = msg.match(
    /RANGER_RS_WIRE_SEND target=([0-9]+) shard=([0-9]+) packet_bytes=18 data=([0-9a-fA-F]{12}) mode=([01])/
  );


  if (send) {
    sends.push({
      emitter:
        id,

      target:
        parseInt(
          send[1]
        ),

      shard:
        parseInt(
          send[2]
        ),

      data:
        send[3].toLowerCase(),

      mode:
        parseInt(
          send[4]
        ),

      time:
        time
    });
  }


  var rx = msg.match(
    /RANGER_RS_WIRE_RX node=([0-9]+) shard=([0-9]+) packet_bytes=18 data=([0-9a-fA-F]{12}) mode=([01])/
  );


  if (rx) {
    receives.push({
      emitter:
        id,

      node:
        parseInt(
          rx[1]
        ),

      shard:
        parseInt(
          rx[2]
        ),

      data:
        rx[3].toLowerCase(),

      mode:
        parseInt(
          rx[4]
        ),

      time:
        time
    });
  }


  var rec = msg.match(
    /RANGER_RS_WIRE_RECONSTRUCT node=([0-9]+) mode=([01]) mask=([0-9]+) payload_match=1/
  );


  if (rec) {
    var recNode =
      parseInt(
        rec[1]
      );


    reconstructed[
      String(recNode)
    ] = true;


    reconstructMask[
      String(recNode)
    ] =
      parseInt(
        rec[3]
      );
  }


  var reject = msg.match(
    /RANGER_RS_WIRE_REJECT node=8 shard=([0-9]+) mode=([01])/
  );


  if (reject) {
    rejected = true;
  }


  var below = msg.match(
    /RANGER_RS_WIRE_BELOW_K node=7 unique=2 mask=3 mode=1/
  );


  if (below) {
    belowK = true;
    belowMask = 3;
  }


  var maskMarker = msg.match(
    /RANGER_RS_WIRE_MASK_PASS mode=([01])/
  );


  if (maskMarker) {
    maskPass = true;
  }


  var allSent = msg.match(
    /RANGER_RS_WIRE_ALL_SHARDS_SENT mode=([01])/
  );


  if (
    allSent &&
    parseInt(
      allSent[1]
    ) === mode
  ) {
    allShardsSent = true;
  }


  var core = msg.match(
    /RANGER_RS_WIRE_CORE_PASS mode=([01]) epoch=1 registered=7 accepted=([0-9]+) rejected=1 below=([0-9]+) bad=0 reports=7/
  );


  if (core) {
    var coreMode =
      parseInt(
        core[1]
      );


    var accepted =
      parseInt(
        core[2]
      );


    var belowCount =
      parseInt(
        core[3]
      );


    if (
      mode === 0 &&
      coreMode === 0 &&
      accepted === 6 &&
      belowCount === 0
    ) {
      corePass = true;
    }


    if (
      mode === 1 &&
      coreMode === 1 &&
      accepted === 5 &&
      belowCount === 1
    ) {
      corePass = true;
    }
  }


  finishIfReady();
}
