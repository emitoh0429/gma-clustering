// ======================================================
// CLEANSCENES.GS
// RAW_SCENES → CLEANED_SCENES
// ======================================================

function cleanRawScenes() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const params = getParametersMap_();

  const rawSheetName = getParam_(params, "RawSheet", DEFAULT_RAW_SHEET_NAME);
  const cleanedSheetName = getParam_(params, "CleanedSheet", DEFAULT_CLEANED_SHEET_NAME);
  const actorFeesSheetName = getParam_(params, "ActorFeesSheet", DEFAULT_ACTOR_FEES_SHEET_NAME);
  const staffFeesSheetName = getParam_(params, "StaffFeesSheet", DEFAULT_STAFF_FEES_SHEET_NAME);
  const locationFeesSheetName = getParam_(params, "LocationFeesSheet", DEFAULT_LOCATION_FEES_SHEET_NAME);

  const rawSheet = getRequiredSheet_(ss, rawSheetName);
  const officialLocations = getOfficialLocations_(locationFeesSheetName);

  let cleanedSheet = ss.getSheetByName(cleanedSheetName);
  if (!cleanedSheet) cleanedSheet = ss.insertSheet(cleanedSheetName);

  cleanedSheet.clearContents();
  cleanedSheet.clearFormats();

  const data = rawSheet.getDataRange().getDisplayValues();
  const headerRowIndex = findHeaderRowIndex_(data);

  if (headerRowIndex === -1) {
    throw new Error("Could not find header row with SEQ, TOD, and LOCATION.");
  }

  const headers = buildEffectiveHeaders_(data, headerRowIndex);
  const upperHeaders = headers.map(h => normalizeForMatch_(h));

  const seqCol = findHeaderCol_(upperHeaders, [
    "SEQ",
    "SEQNO",
    "SEQNUM",
    "SEQUENCE"
  ]);

  const todCol = findHeaderCol_(upperHeaders, [
    "TOD",
    "TIMEOFDAY",
    "TIME OF DAY",
  ]);

  const locationCol = findHeaderCol_(upperHeaders, [
    "LOCATION",
    "LOC"
  ]);

  const descriptionCol = findHeaderCol_(upperHeaders, [
    "DESCRIPTION",
    "SCENEDESC",
    "DESC"
  ]);

  const heavyCol = upperHeaders.findIndex(h =>
    h.replace(/[^A-Z]/g, "").startsWith("HEAVY")
  );

  if (seqCol === -1) throw new Error("Missing SEQ / SEQ.NO. column");
  if (todCol === -1) throw new Error("Missing TOD / Time Of Day column");
  if (locationCol === -1) throw new Error("Missing LOCATION column");

  const actorNames = getActorNamesFromFeesSheet_(actorFeesSheetName);
  const staffNames = getSpecificDayStaffNamesFromFeesSheet_(staffFeesSheetName);

  const actorCols = actorNames
    .map(actor => ({
      name: actor,
      index: findBestHeaderIndex_(headers, actor)
    }))
    .filter(item => item.index !== -1);

  const staffCols = staffNames
    .map(staff => ({
      name: staff,
      index: findBestHeaderIndex_(headers, staff)
    }))
    .filter(item => item.index !== -1);

  const firstDataRowIndex = getFirstDataRowIndex_(data, headerRowIndex);

  const output = [[
    "SceneID",
    "Type",
    "TimeOfDay",
    "Location",
    "LocationDetail",
    "Actors",
    "StaffNeeded",
    "Description"
  ]];

  for (let r = firstDataRowIndex; r < data.length; r++) {
    const row = data[r];

    const sceneId = cleanCell_(row[seqCol]);
    const rawTOD = cleanCell_(row[todCol]);
    const rawLocation = cleanCell_(row[locationCol]);
    const description = descriptionCol !== -1 ? cleanCell_(row[descriptionCol]) : "";

    if (!sceneId || !rawLocation) continue;

    const timeOfDay = parseTimeOfDay_(rawTOD);
    const locationParts = splitLocation_(rawLocation, officialLocations);
    const fullRowText = normalizeForMatch_(row.join(" "));

    let type = "Light";

    if (heavyCol !== -1) {
      type = isChecked_(row[heavyCol]) ? "Heavy" : "Light";
    } else {
      type = /\bHEAVY\b/.test(fullRowText) ? "Heavy" : "Light";
    }

    const actors = [];
    actorCols.forEach(actor => {
      if (isCheckedOrFilled_(row[actor.index])) {
        actors.push(actor.name);
      }
    });

    const staffNeeded = [];
    staffCols.forEach(staff => {
      if (isCheckedOrFilled_(row[staff.index])) {
        staffNeeded.push(staff.name);
      }
    });

    output.push([
      sceneId,
      type,
      timeOfDay,
      locationParts.broadLocation,
      locationParts.locationDetail,
      actors.join(", "),
      staffNeeded.join(", "),
      description
    ]);
  }

  const cleanedRange = cleanedSheet.getRange(1, 1, output.length, output[0].length);
  cleanedRange.setNumberFormat("@");
  cleanedRange.setValues(output);

  formatBlackHeader_(cleanedSheet.getRange(1, 1, 1, output[0].length));
  formatCleanedScenesSheet_(cleanedSheet, output.length, output[0].length);
}
