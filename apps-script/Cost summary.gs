// ======================================================
// COSTSUMMARY.GS
// CLUSTERING_OUTPUT + FEES → SPECIALIZED_COSTS
// Dynamic number of days + Specialized Staff + Fixed Staff
// ======================================================

function createCostSummary() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const params = getParametersMap_();

  const clusteringOutputSheetName = getParam_(
    params,
    "ClusteringOutputSheet",
    DEFAULT_CLUSTERING_OUTPUT_SHEET_NAME
  );

  const costSummarySheetName = getParam_(
    params,
    "CostSummarySheet",
    DEFAULT_COST_SUMMARY_SHEET_NAME
  );

  const actorFeesSheetName = getParam_(
    params,
    "ActorFeesSheet",
    DEFAULT_ACTOR_FEES_SHEET_NAME
  );

  const staffFeesSheetName = getParam_(
    params,
    "StaffFeesSheet",
    DEFAULT_STAFF_FEES_SHEET_NAME
  );

  const locationFeesSheetName = getParam_(
    params,
    "LocationFeesSheet",
    DEFAULT_LOCATION_FEES_SHEET_NAME
  );

  const clusteringSheet = getRequiredSheet_(ss, clusteringOutputSheetName);

  let summarySheet = ss.getSheetByName(costSummarySheetName);
  if (!summarySheet) summarySheet = ss.insertSheet(costSummarySheetName);

  // Clear ONLY A:E so it will not overwrite your groupmate's right-side table.
  summarySheet.getRange("A:E").clearContent();
  summarySheet.getRange("A:E").clearFormat();
  summarySheet.setFrozenRows(0);

  // ======================================================
  // 0. READ CLUSTERING_OUTPUT SAFELY
  // ======================================================

  const rawValues = clusteringSheet.getDataRange().getDisplayValues();

  if (rawValues.length < 2) {
    summarySheet.getRange(1, 1).setValue("No CLUSTERING_OUTPUT data found.");
    return;
  }

  // Find actual header row.
  // This prevents warning rows like "MaxDays was infeasible..." from being treated as headers.
  let headerRowIndex = -1;

  for (let r = 0; r < rawValues.length; r++) {
    const normalizedRow = rawValues[r].map(h => normalizeForMatch_(h));

    const hasSceneId =
      normalizedRow.includes("SCENEID") ||
      normalizedRow.includes("SEQ") ||
      normalizedRow.includes("SEQNO") ||
      normalizedRow.includes("SEQNUM") ||
      normalizedRow.includes("SEQUENCE");

    const hasLocation =
      normalizedRow.includes("LOCATION") ||
      normalizedRow.includes("LOC");

    if (hasSceneId && hasLocation) {
      headerRowIndex = r;
      break;
    }
  }

  if (headerRowIndex === -1) {
    summarySheet.getRange(1, 1).setValue("No valid CLUSTERING_OUTPUT header found.");
    return;
  }

  // Only use rows from the real header downward.
  const values = rawValues.slice(headerRowIndex);

  if (values.length < 2) {
    summarySheet.getRange(1, 1).setValue("No schedule rows found below CLUSTERING_OUTPUT header.");
    return;
  }

  const headers = values[0].map(h => normalizeForMatch_(h));

  const sceneIdCol = findHeaderCol_(headers, [
    "SCENEID",
    "SEQ",
    "SEQNO",
    "SEQNUM",
    "SEQUENCE"
  ]);

  const locationCol = findHeaderCol_(headers, [
    "LOCATION",
    "LOC"
  ]);

  const actorsCol = findHeaderCol_(headers, [
    "ACTORS",
    "ACTOR",
    "CAST",
    "CHARACTERS"
  ]);

  const staffCol = findHeaderCol_(headers, [
    "STAFFNEEDED",
    "STAFF",
    "CREW"
  ]);

  if (sceneIdCol === -1) {
    throw new Error("Missing SceneID column in " + clusteringOutputSheetName);
  }

  const locationFeeMap = getFeeMapAsNumber_(locationFeesSheetName, [
    "LOCATION",
    "LOC",
    "LOCATIONNAME",
    "NAME"
  ]);

  const actorFeeMap = getFeeMapAsNumber_(actorFeesSheetName, [
    "ACTOR",
    "ACTORNAME",
    "ACTORS",
    "CAST",
    "CHARACTER",
    "CHARACTERNAME",
    "NAME"
  ]);

  const staffFeeMap = getFeeMapAsNumber_(staffFeesSheetName, [
    "STAFF",
    "STAFFNAME",
    "STAFFGROUP",
    "STAFFTYPE",
    "CREW",
    "NAME"
  ]);

  // ======================================================
  // 1. DAILY VARIABLE COSTS
  // Counts each Location / Actor / Specialized Staff ONCE PER DAY
  // ======================================================

  const dayTotals = {};
  const dayOrder = [];
  const seenDayNumbers = {};

  let currentDayNumber = null;

  for (let r = 1; r < values.length; r++) {
    const row = values[r];

    const sceneId = cleanCell_(row[sceneIdCol]);
    const sceneKey = normalizeForMatch_(sceneId);

    if (!sceneId) continue;

    // DAY row from CLUSTERING_OUTPUT
    if (sceneKey.startsWith("DAY")) {
      const match = sceneKey.match(/DAY\s*(\d+)/);

      if (match) {
        currentDayNumber = Number(match[1]);

        if (!dayTotals[currentDayNumber]) {
          dayTotals[currentDayNumber] = {
            location: 0,
            actor: 0,
            specializedStaff: 0,

            // Prevent duplicate charging within the same day
            seenLocations: {},
            seenActors: {},
            seenStaff: {}
          };
        }

        // Prevent duplicate day count if DAY row somehow appears twice
        if (!seenDayNumbers[currentDayNumber]) {
          dayOrder.push(currentDayNumber);
          seenDayNumbers[currentDayNumber] = true;
        }
      }

      continue;
    }

    // Ignore rows before the first DAY row
    if (!currentDayNumber) continue;

    const location = locationCol !== -1 ? cleanCell_(row[locationCol]) : "";
    const actors = actorsCol !== -1 ? splitCommaNames_(row[actorsCol]) : [];
    const staffList = staffCol !== -1 ? splitCommaNames_(row[staffCol]) : [];

    // Location: charge once per day
    if (location) {
      const locationKey = normalizeForMatch_(location);

      if (!dayTotals[currentDayNumber].seenLocations[locationKey]) {
        dayTotals[currentDayNumber].location += getFeeForNameAsNumber_(
          location,
          locationFeeMap
        );

        dayTotals[currentDayNumber].seenLocations[locationKey] = true;
      }
    }

    // Actors: charge each actor once per day
    actors.forEach(actor => {
      if (!actor) return;

      const actorKey = normalizeForMatch_(actor);

      if (!dayTotals[currentDayNumber].seenActors[actorKey]) {
        dayTotals[currentDayNumber].actor += getFeeForNameAsNumber_(
          actor,
          actorFeeMap
        );

        dayTotals[currentDayNumber].seenActors[actorKey] = true;
      }
    });

    // Specialized Staff: charge each checked/specialized staff once per day
    staffList.forEach(staffName => {
      if (!staffName) return;

      const staffKey = normalizeForMatch_(staffName);

      if (!dayTotals[currentDayNumber].seenStaff[staffKey]) {
        dayTotals[currentDayNumber].specializedStaff += getFeeForNameAsNumber_(
          staffName,
          staffFeeMap
        );

        dayTotals[currentDayNumber].seenStaff[staffKey] = true;
      }
    });
  }

  if (dayOrder.length === 0) {
    summarySheet.getRange(1, 1).setValue("No DAY rows found in CLUSTERING_OUTPUT.");
    return;
  }

  const sortedDays = [...new Set(dayOrder)].sort((a, b) => a - b);
  const numberOfShootDays = sortedDays.length;

  // ======================================================
  // 2. FIXED STAFF COSTS
  // Fixed Staff = STAFF_FEES rows where "Only in Specific Days?" is unchecked/blank.
  // Counted every shoot day, then spread equally per day in the left summary.
  // ======================================================

  const fixedStaffTotal = getFixedStaffTotal_(
    staffFeesSheetName,
    numberOfShootDays
  );

  const fixedStaffPerDay = numberOfShootDays > 0
    ? fixedStaffTotal / numberOfShootDays
    : 0;

  // ======================================================
  // 3. LEFT SUMMARY TABLE ONLY
  // ======================================================

  const output = [];

  output.push(["SUMMARY SHEET - COSTS PER DAY", "", "", "", ""]);
  output.push(["DAY", "Location", "Actor", "Specialized Staff", "Fixed Staff"]);

  let totalLocation = 0;
  let totalActor = 0;
  let totalSpecializedStaff = 0;
  let totalFixedStaff = 0;

  for (const day of sortedDays) {
    const locationCost = dayTotals[day].location;
    const actorCost = dayTotals[day].actor;
    const specializedStaffCost = dayTotals[day].specializedStaff;
    const fixedStaffCost = fixedStaffPerDay;

    totalLocation += locationCost;
    totalActor += actorCost;
    totalSpecializedStaff += specializedStaffCost;
    totalFixedStaff += fixedStaffCost;

    output.push([
      day,
      locationCost,
      actorCost,
      specializedStaffCost,
      fixedStaffCost
    ]);
  }

  const totalCost =
    totalLocation +
    totalActor +
    totalSpecializedStaff +
    totalFixedStaff;

  output.push([
    "TOTAL/AREA",
    totalLocation,
    totalActor,
    totalSpecializedStaff,
    totalFixedStaff
  ]);

  output.push([
    "TOTAL COST",
    totalCost,
    "",
    "",
    ""
  ]);

  summarySheet.getRange(1, 1, output.length, 5).setValues(output);

  formatProjectedCostSheet_(summarySheet, output.length, 5);
}


// ======================================================
// FIXED STAFF TOTAL
// Fixed staff = unchecked / blank in "Only in Specific Days?"
// Checked = specialized staff, handled through CLUSTERING_OUTPUT.
// Does NOT write any breakdown table.
// ======================================================

function getFixedStaffTotal_(staffFeesSheetName, numberOfShootDays) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = getRequiredSheet_(ss, staffFeesSheetName);

  const lastRow = sheet.getLastRow();
  const lastCol = sheet.getLastColumn();

  if (lastRow < 2 || lastCol < 1) return 0;

  const headers = sheet
    .getRange(1, 1, 1, lastCol)
    .getDisplayValues()[0];

  const normalizedHeaders = headers.map(h =>
    String(h || "")
      .toUpperCase()
      .replace(/[^A-Z0-9]/g, "")
      .trim()
  );

  const staffCol = normalizedHeaders.findIndex(h =>
    h === "STAFF" ||
    h === "STAFFNAME" ||
    h === "STAFFGROUP" ||
    h === "STAFFTYPE" ||
    h === "CREW" ||
    h === "NAME"
  );

  const costCol = normalizedHeaders.findIndex(h =>
    h === "COST" ||
    h === "FEE" ||
    h === "RATE" ||
    h === "RATEDAY" ||
    h === "RATEPERDAY" ||
    h === "DAILYRATE" ||
    h === "PRICE" ||
    h === "AMOUNT"
  );

  const specificCol = normalizedHeaders.findIndex(h =>
    h === "ONLYINSPECIFICDAYS" ||
    h === "ONLYSPECIFICDAYS" ||
    h === "SPECIFICDAYS" ||
    h === "SPECIFICDAY" ||
    h.includes("ONLYINSPECIFICDAYS") ||
    h.includes("SPECIFICDAYS")
  );

  if (staffCol === -1) {
    throw new Error(
      "Missing Staff column in " +
      staffFeesSheetName +
      ". Found headers: " +
      headers.join(" | ")
    );
  }

  if (costCol === -1) {
    throw new Error(
      "Missing Cost/Fee/Rate column in " +
      staffFeesSheetName +
      ". Found headers: " +
      headers.join(" | ")
    );
  }

  if (specificCol === -1) {
    throw new Error(
      "Missing 'Only in Specific Days?' column in " +
      staffFeesSheetName +
      ". Found headers: " +
      headers.join(" | ")
    );
  }

  const data = sheet
    .getRange(2, 1, lastRow - 1, lastCol)
    .getDisplayValues();

  let total = 0;

  data.forEach(row => {
    const staffName = cleanCell_(row[staffCol]);
    const ratePerDay = parseMoneyNumber_(row[costCol]);

    const onlySpecificDays =
      row[specificCol] === true ||
      isChecked_(row[specificCol]);

    if (!staffName) return;

    // Checked = specialized staff.
    // Unchecked / blank = fixed staff, counted every shoot day.
    if (onlySpecificDays) return;

    total += ratePerDay * numberOfShootDays;
  });

  return total;
}
