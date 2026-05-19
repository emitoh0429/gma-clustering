// ======================================================
// CLEANED FOR COSTS.GS
// CLUSTERING_OUTPUT → CLEANED FOR COSTS
// Detailed day-by-day cost table:
// DAY 1
// Location | Cost | Actor | Cost | Staff | Cost
// ======================================================

function createCleanedForCosts() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();

  const clusteringSheet = getRequiredSheet_(ss, DEFAULT_CLUSTERING_OUTPUT_SHEET_NAME);

  let cleanedForCostsSheet = ss.getSheetByName(DEFAULT_CLEANED_FOR_COSTS_SHEET_NAME);
  if (!cleanedForCostsSheet) {
    cleanedForCostsSheet = ss.insertSheet(DEFAULT_CLEANED_FOR_COSTS_SHEET_NAME);
  }

  cleanedForCostsSheet.clearContents();
  cleanedForCostsSheet.clearFormats();
  cleanedForCostsSheet.setFrozenRows(0);

  const values = clusteringSheet.getDataRange().getDisplayValues();

  if (!values || values.length < 2) {
    cleanedForCostsSheet.getRange(1, 1).setValue("No data found.");
    return;
  }

  const headers = values[0].map(h => normalizeForMatch_(h));

  const sceneIdCol = findHeaderCol_(headers, ["SCENEID", "SEQ", "SEQNO", "SEQUENCE"]);
  const locationCol = findHeaderCol_(headers, ["LOCATION", "LOC"]);
  const actorsCol = findHeaderCol_(headers, ["ACTORS", "ACTOR", "CAST", "CHARACTERS"]);
  const staffCol = findHeaderCol_(headers, ["STAFFNEEDED", "STAFF", "CREW"]);

  if (sceneIdCol === -1) throw new Error("Missing SceneID column in CLUSTERING_OUTPUT.");
  if (locationCol === -1) throw new Error("Missing Location column in CLUSTERING_OUTPUT.");
  if (actorsCol === -1) throw new Error("Missing Actors column in CLUSTERING_OUTPUT.");
  if (staffCol === -1) throw new Error("Missing StaffNeeded column in CLUSTERING_OUTPUT.");

  const locationFeeMap = getFeeMapAsNumber_(DEFAULT_LOCATION_FEES_SHEET_NAME, [
    "LOCATION",
    "LOC",
    "LOCATIONNAME"
  ]);

  const actorFeeMap = getFeeMapAsNumber_(DEFAULT_ACTOR_FEES_SHEET_NAME, [
    "ACTOR",
    "ACTORS",
    "CAST",
    "CHARACTER",
    "NAME",
    "ACTORNAME"
  ]);

  const staffFeeMap = getFeeMapAsNumber_(DEFAULT_STAFF_FEES_SHEET_NAME, [
    "STAFF",
    "STAFFNAME",
    "STAFFGROUP",
    "STAFFTYPE",
    "CREW",
    "NAME"
  ]);

  const days = [];
  let currentDay = null;

  for (let r = 1; r < values.length; r++) {
    const firstCell = cleanCell_(values[r][0]);
    const firstNorm = normalizeForMatch_(firstCell);

    if (/^DAY [0-9]+$/.test(firstNorm)) {
      currentDay = {
        label: firstNorm,
        locations: {},
        actors: {},
        staff: {}
      };
      days.push(currentDay);
      continue;
    }

    if (!currentDay) continue;

    const sceneId = cleanCell_(values[r][sceneIdCol]);
    if (!sceneId) continue;

    const location = cleanCell_(values[r][locationCol]);
    const actors = splitCommaNames_(values[r][actorsCol]);
    const staffNeeded = splitCommaNames_(values[r][staffCol]);

    if (location) {
      const locationKey = normalizeForMatch_(location);
      if (!currentDay.locations[locationKey]) {
        currentDay.locations[locationKey] = {
          name: location,
          cost: getFeeForNameAsNumber_(location, locationFeeMap)
        };
      }
    }

    actors.forEach(actor => {
      const actorKey = normalizeForMatch_(actor);
      if (!actorKey) return;

      if (!currentDay.actors[actorKey]) {
        currentDay.actors[actorKey] = {
          name: actor,
          cost: getFeeForNameAsNumber_(actor, actorFeeMap)
        };
      }
    });

    staffNeeded.forEach(staff => {
      const staffKey = normalizeForMatch_(staff);
      if (!staffKey) return;

      if (!currentDay.staff[staffKey]) {
        currentDay.staff[staffKey] = {
          name: staff,
          cost: getFeeForNameAsNumber_(staff, staffFeeMap)
        };
      }
    });
  }

  if (days.length === 0) {
    cleanedForCostsSheet.getRange(1, 1).setValue("No DAY sections found in CLUSTERING_OUTPUT.");
    return;
  }

  const blockWidth = 6;
  const spacerWidth = 1;
  const maxRowsPerDay = Math.max(...days.map(day => {
    return Math.max(
      Object.keys(day.locations).length,
      Object.keys(day.actors).length,
      Object.keys(day.staff).length
    );
  }));

  const totalRows = maxRowsPerDay + 2;
  const totalCols = days.length * blockWidth + (days.length - 1) * spacerWidth;

  const output = Array.from({ length: totalRows }, () =>
    Array.from({ length: totalCols }, () => "")
  );

  days.forEach((day, dayIndex) => {
    const startCol = dayIndex * (blockWidth + spacerWidth);

    output[0][startCol] = day.label;
    output[1][startCol] = "Location";
    output[1][startCol + 1] = "Cost";
    output[1][startCol + 2] = "Actor";
    output[1][startCol + 3] = "Cost";
    output[1][startCol + 4] = "Staff";
    output[1][startCol + 5] = "Cost";

    const locations = Object.values(day.locations);
    const actors = Object.values(day.actors);
    const staff = Object.values(day.staff);

    for (let i = 0; i < maxRowsPerDay; i++) {
      const row = i + 2;

      if (locations[i]) {
        output[row][startCol] = locations[i].name;
        output[row][startCol + 1] = locations[i].cost;
      }

      if (actors[i]) {
        output[row][startCol + 2] = actors[i].name;
        output[row][startCol + 3] = actors[i].cost;
      }

      if (staff[i]) {
        output[row][startCol + 4] = staff[i].name;
        output[row][startCol + 5] = staff[i].cost;
      }
    }
  });

  const range = cleanedForCostsSheet.getRange(1, 1, totalRows, totalCols);
  range.setValues(output);

  formatCleanedForCostsSheet_(cleanedForCostsSheet, totalRows, totalCols, days.length);
}

