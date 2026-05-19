// ======================================================
// CLUSTERING.GS
// CLEANED_SCENES → API → OUTPUT → CLUSTERING_OUTPUT
// ======================================================

function runClustering() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const params = getParametersMap_();

  const optimizerUrl = getRequiredParameter_(params, "OptimizerURL");

  const cleanedSheet = getRequiredSheet_(ss, DEFAULT_CLEANED_SHEET_NAME);
  const actorSheet = getRequiredSheet_(ss, DEFAULT_ACTOR_FEES_SHEET_NAME);
  const staffSheet = getRequiredSheet_(ss, DEFAULT_STAFF_FEES_SHEET_NAME);
  const locationSheet = getRequiredSheet_(ss, DEFAULT_LOCATION_FEES_SHEET_NAME);
  const parameterSheet = getRequiredSheet_(ss, DEFAULT_PARAMETERS_SHEET_NAME);

  clearClusteringFeasibilityBox_(parameterSheet);
  validateAllLocationsAssignedToGroups_();

  const locationGroups =
    typeof readLocationGroups_ === "function"
      ? readLocationGroups_()
      : [];

  let outputSheet = ss.getSheetByName(DEFAULT_OUTPUT_SHEET_NAME);
  if (!outputSheet) outputSheet = ss.insertSheet(DEFAULT_OUTPUT_SHEET_NAME);

  outputSheet.clearContents();
  outputSheet.clearFormats();
  outputSheet.setFrozenRows(0);

  const userMaxDays = getOptionalMaxDaysFromParameterSheet_(parameterSheet);

  const payload = {
    scenes: cleanedSheet.getDataRange().getValues(),
    actors: convertCostLikeColumnsToNumbers_(actorSheet.getDataRange().getValues()),
    staff: convertCostLikeColumnsToNumbers_(staffSheet.getDataRange().getValues()),
    locations: convertCostLikeColumnsToNumbers_(locationSheet.getDataRange().getValues()),
    parameter: convertCostLikeColumnsToNumbers_(parameterSheet.getDataRange().getValues()),
    location_groups: locationGroups
  };

  const response = UrlFetchApp.fetch(optimizerUrl, {
    method: "post",
    contentType: "application/json",
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  });

  const responseCode = response.getResponseCode();
  const responseText = response.getContentText();

  Logger.log("Response code: " + responseCode);
  Logger.log(responseText);

  if (responseCode < 200 || responseCode >= 300) {
    outputSheet.getRange(1, 1).setValue("API ERROR " + responseCode);
    outputSheet.getRange(2, 1).setValue(responseText);
    outputSheet.getRange(2, 1).setWrap(true);

    writeClusteringFeasibilityBox_(
      parameterSheet,
      "ERROR",
      "API ERROR " + responseCode + ". Check OUTPUT row 2, Render logs, or OptimizerURL."
    );

    ss.toast(
      "API ERROR " + responseCode + ". Check OUTPUT row 2.",
      "Clustering Error",
      8
    );

    autoFitOutputSheet_(outputSheet);
    return;
  }

  let result;

  try {
    result = JSON.parse(responseText);
  } catch (err) {
    outputSheet.getRange(1, 1).setValue("API did not return valid JSON");
    outputSheet.getRange(2, 1).setValue(responseText);
    outputSheet.getRange(2, 1).setWrap(true);

    writeClusteringFeasibilityBox_(
      parameterSheet,
      "ERROR",
      "API did not return valid JSON."
    );

    ss.toast(
      "API did not return valid JSON.",
      "Clustering Error",
      8
    );

    autoFitOutputSheet_(outputSheet);
    return;
  }

  if (result.error) {
    outputSheet.getRange(1, 1).setValue("ERROR");
    outputSheet.getRange(2, 1).setValue(result.error);
    outputSheet.getRange(2, 1).setWrap(true);

    writeClusteringFeasibilityBox_(
      parameterSheet,
      "ERROR",
      result.error
    );

    ss.toast(
      result.error,
      "Clustering Error",
      8
    );

    autoFitOutputSheet_(outputSheet);
    return;
  }

  if (!result.schedule || result.schedule.length === 0) {
    outputSheet.getRange(1, 1).setValue("NO SCHEDULE RETURNED");
    outputSheet.getRange(2, 1).setValue(JSON.stringify(result));
    outputSheet.getRange(2, 1).setWrap(true);

    writeClusteringFeasibilityBox_(
      parameterSheet,
      "ERROR",
      "No schedule returned by optimizer."
    );

    ss.toast(
      "No schedule returned by optimizer.",
      "Clustering Error",
      8
    );

    autoFitOutputSheet_(outputSheet);
    return;
  }

  const usedFallback = result.used_fallback === true;
  const finalDays = Number(result.final_days || result.schedule.length);

  let startRow = 1;

  // ======================================================
  // CASE 1: No MaxDays
  // ======================================================
  if (userMaxDays === null) {
    const msg = "No MaxDays set. Solved with MaxDays constraint effectively off.";

    writeClusteringFeasibilityBox_(
      parameterSheet,
      "OK",
      msg
    );

    ss.toast(
      msg,
      "Clustering Feasibility",
      5
    );
  }

  // ======================================================
  // CASE 3: MaxDays input was infeasible.
  // Python used minimum required days.
  // ======================================================
  else if (!result.is_user_days_feasible) {
    const msg =
      "MaxDays = " +
      result.user_max_days +
      " was infeasible. Minimum required days found: " +
      result.D_min +
      ".";

    outputSheet.getRange(1, 1).setValue(
      msg + " Schedule below uses MaxDays = " + result.D_min + "."
    );
    
    outputSheet.getRange(1, 1)
      .setFontWeight("bold")
      .setBackground("#fff2cc")
      .setWrap(true);

    writeClusteringFeasibilityBox_(
      parameterSheet,
      "WARNING",
      msg
    );

    ss.toast(
      "MaxDays was infeasible. Used minimum required days: " + finalDays + ".",
      "Clustering Feasibility",
      8
    );

    startRow = 3;
  }

  // ======================================================
  // CASE 2: MaxDays input was feasible.
  // ======================================================
  else {
    const msg = "Feasible within MaxDays = " + userMaxDays + ".";

    writeClusteringFeasibilityBox_(
      parameterSheet,
      "OK",
      msg
    );

    ss.toast(
      msg,
      "Clustering Feasibility",
      5
    );
  }

  writeScheduleToOutput_(outputSheet, result.schedule, startRow);
}


// ======================================================
// PARAMETER HELPERS
// ======================================================

function getOptionalMaxDaysFromParameterSheet_(parameterSheet) {
  const values = parameterSheet.getDataRange().getValues();

  for (let r = 1; r < values.length; r++) {
    const key = String(values[r][0] || "").trim();

    if (key === "MaxDays") {
      const rawValue = values[r][1];

      if (rawValue === "" || rawValue === null || rawValue === undefined) {
        return null;
      }

      const value = Number(rawValue);

      if (!value || value < 1) {
        return null;
      }

      return value;
    }
  }

  return null;
}


// ======================================================
// OUTPUT WRITER
// ======================================================

function writeScheduleToOutput_(outputSheet, schedule, startRow) {
  const numRows = schedule.length;
  const numCols = Math.max(...schedule.map(row =>
    Array.isArray(row) ? row.length : 1
  ));

  const normalized = schedule.map(row => {
    const newRow = Array.isArray(row) ? [...row] : [row];

    while (newRow.length < numCols) {
      newRow.push("");
    }

    return newRow.map(v => (v === null || v === undefined) ? "" : String(v));
  });

  const outputRange = outputSheet.getRange(startRow, 1, numRows, numCols);
  outputRange.setNumberFormat("@");
  outputRange.setValues(normalized);

  outputRange
    .setHorizontalAlignment("center")
    .setVerticalAlignment("middle")
    .setWrap(false)
    .setFontWeight("normal");

  outputSheet.getRange(startRow, 1, numRows, 1)
    .setHorizontalAlignment("left")
    .setFontWeight("bold");

  autoFitOutputSheet_(outputSheet);
}


// ======================================================
// CLUSTERING FEASIBILITY BOX
// I4:K6 status box on PARAMETERS sheet
// ======================================================

function clearClusteringFeasibilityBox_(sheet) {
  sheet.getRange("I4:K6")
    .clearContent()
    .clearFormat()
    .clearDataValidations()
    .breakApart();
}


function writeClusteringFeasibilityBox_(sheet, status, message) {
  clearClusteringFeasibilityBox_(sheet);

  const titleRange = sheet.getRange("I4:K4");
  const messageRange = sheet.getRange("I5:K6");

  titleRange
    .merge()
    .setValue("Clustering Feasibility Check")
    .setFontWeight("bold")
    .setFontSize(10)
    .setHorizontalAlignment("center")
    .setVerticalAlignment("middle")
    .setWrap(true);

  messageRange
    .merge()
    .setValue(message)
    .setFontSize(9)
    .setHorizontalAlignment("center")
    .setVerticalAlignment("middle")
    .setWrap(true);

  sheet.getRange("I4:K6")
    .setBorder(true, true, true, true, true, true);

  if (status === "OK") {
    sheet.getRange("I4:K6").setBackground("#d9ead3");
  } else if (status === "WARNING") {
    sheet.getRange("I4:K6").setBackground("#fff2cc");
  } else {
    sheet.getRange("I4:K6").setBackground("#f4cccc");
  }

  sheet.setRowHeight(4, 32);
  sheet.setRowHeight(5, 42);
  sheet.setRowHeight(6, 42);

  sheet.setColumnWidth(9, 130);  // I
  sheet.setColumnWidth(10, 130); // J
  sheet.setColumnWidth(11, 130); // K
}


// ======================================================
// CREATE DETAILED CLUSTERING OUTPUT
// OUTPUT → CLUSTERING_OUTPUT
// ======================================================

function createClusteringOutput() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const params = getParametersMap_();

  const outputSheetName = getParam_(
    params,
    "OutputSheet",
    DEFAULT_OUTPUT_SHEET_NAME
  );

  const cleanedSheetName = getParam_(
    params,
    "CleanedSheet",
    DEFAULT_CLEANED_SHEET_NAME
  );

  const clusteringOutputSheetName = getParam_(
    params,
    "ClusteringOutputSheet",
    DEFAULT_CLUSTERING_OUTPUT_SHEET_NAME
  );

  const outputSheet = getRequiredSheet_(ss, outputSheetName);
  const cleanedSheet = getRequiredSheet_(ss, cleanedSheetName);

  let clusteringSheet = ss.getSheetByName(clusteringOutputSheetName);
  if (!clusteringSheet) clusteringSheet = ss.insertSheet(clusteringOutputSheetName);

  clusteringSheet.clearContents();
  clusteringSheet.clearFormats();
  clusteringSheet.setFrozenRows(0);

  const scheduleValues = outputSheet.getDataRange().getDisplayValues();
  const cleanedValues = cleanedSheet.getDataRange().getDisplayValues();

  if (scheduleValues.length === 0 || cleanedValues.length < 2) {
    clusteringSheet.getRange(1, 1).setValue("No data found.");
    return;
  }

  const cleanedHeaderKeys = cleanedValues[0].map(h => normalizeForMatch_(h));

  const sceneIdCol = findHeaderCol_(cleanedHeaderKeys, [
    "SCENEID",
    "SEQ",
    "SEQNO",
    "SEQNUM",
    "SEQUENCE"
  ]);

  const typeCol = findHeaderCol_(cleanedHeaderKeys, [
    "TYPE"
  ]);

  const timeOfDayCol = findHeaderCol_(cleanedHeaderKeys, [
    "TIMEOFDAY",
    "TOD",
    "TIME"
  ]);

  const locationCol = findHeaderCol_(cleanedHeaderKeys, [
    "LOCATION",
    "LOC"
  ]);

  const locationDetCol = findHeaderCol_(cleanedHeaderKeys, [
    "LOCATIONDETAIL",
    "LOCATIONDETAILS",
    "DETAILLOCATION"
  ]);

  const actorsCol = findHeaderCol_(cleanedHeaderKeys, [
    "ACTORS",
    "CAST",
    "CHARACTERS"
  ]);

  const staffCol = findHeaderCol_(cleanedHeaderKeys, [
    "STAFFNEEDED",
    "STAFF",
    "CREW"
  ]);

  const descCol = findHeaderCol_(cleanedHeaderKeys, [
    "DESCRIPTION",
    "DETAILS",
    "SCENEDESCRIPTION",
    "SCENEDESC",
    "DESC"
  ]);

  if (sceneIdCol === -1) {
    throw new Error("Missing SceneID column in " + cleanedSheetName);
  }

  const sceneMap = {};

  for (let r = 1; r < cleanedValues.length; r++) {
    const row = cleanedValues[r];
    const sceneId = cleanCell_(row[sceneIdCol]);

    if (!sceneId) continue;

    sceneMap[normalizeSceneKey_(sceneId)] = {
      sceneId: sceneId,
      type: typeCol !== -1 ? cleanCell_(row[typeCol]) : "",
      timeOfDay: timeOfDayCol !== -1 ? cleanCell_(row[timeOfDayCol]) : "",
      location: locationCol !== -1 ? cleanCell_(row[locationCol]) : "",
      locationDetail: locationDetCol !== -1 ? cleanCell_(row[locationDetCol]) : "",
      actors: actorsCol !== -1 ? cleanCell_(row[actorsCol]) : "",
      staffNeeded: staffCol !== -1 ? cleanCell_(row[staffCol]) : "",
      description: descCol !== -1 ? cleanCell_(row[descCol]) : ""
    };
  }

  const finalOutput = [[
    "SceneID",
    "Type",
    "TimeOfDay",
    "Location",
    "LocationDetail",
    "Actors",
    "StaffNeeded",
    "Description"
  ]];

  scheduleValues.forEach(scheduleRow => {
    const dayLabel = cleanCell_(scheduleRow[0]);

    if (!dayLabel || !normalizeForMatch_(dayLabel).startsWith("DAY")) return;

    finalOutput.push([dayLabel.toUpperCase(), "", "", "", "", "", "", ""]);

    for (let c = 1; c < scheduleRow.length; c++) {
      const rawSceneId = cleanCell_(scheduleRow[c]);

      if (!rawSceneId) continue;

      const scene = sceneMap[normalizeSceneKey_(rawSceneId)];

      if (scene) {
        finalOutput.push([
          scene.sceneId,
          scene.type,
          scene.timeOfDay,
          scene.location,
          scene.locationDetail,
          scene.actors,
          scene.staffNeeded,
          scene.description
        ]);
      } else {
        finalOutput.push([
          rawSceneId,
          "NOT FOUND IN CLEANED_SCENES",
          "",
          "",
          "",
          "",
          "",
          ""
        ]);
      }
    }

    finalOutput.push(["", "", "", "", "", "", "", ""]);
  });

  if (finalOutput.length > 1) finalOutput.pop();

  const range = clusteringSheet.getRange(
    1,
    1,
    finalOutput.length,
    finalOutput[0].length
  );

  range.setNumberFormat("@");
  range.setValues(finalOutput);

  formatClusteringOutputSheet_(
    clusteringSheet,
    finalOutput.length,
    finalOutput[0].length
  );
}


// ======================================================
// MONEY / NUMBER CLEANING HELPERS FOR API PAYLOAD
// Keep these here only if they are not already in Helpers.gs.
// ======================================================

function convertCostLikeColumnsToNumbers_(values) {
  if (!values || values.length === 0) return values;

  const headers = values[0].map(h => normalizeForMatch_(h));
  const costLikeColumns = headers.map(h => isCostLikeHeader_(h));

  return values.map((row, r) => {
    if (r === 0) return row;

    return row.map((cell, c) => {
      if (!costLikeColumns[c]) return cell;

      if (cell === "" || cell === null || cell === undefined) return 0;

      return parseMoneyNumber_(cell);
    });
  });
}


function isCostLikeHeader_(header) {
  const h = normalizeForMatch_(header);

  return (
    h === "COST" ||
    h === "FEE" ||
    h === "RATE" ||
    h === "PRICE" ||
    h === "AMOUNT" ||
    h === "BUDGET" ||
    h === "MAXBUDGET" ||
    h === "MAXCOST" ||
    h === "DAILYCOST" ||
    h === "DAILYRATE" ||
    h.includes("COST") ||
    h.includes("FEE") ||
    h.includes("RATE") ||
    h.includes("PRICE") ||
    h.includes("AMOUNT") ||
    h.includes("BUDGET")
  );
}
