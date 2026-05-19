// ======================================================
// CLEAN + CHECK FEASIBILITY
// Button 1 should be assigned to: cleanAndCheck
// ======================================================


// ======================================================
// CHECK FEASIBILITY
// Reads PARAMETERS + CLEANED_SCENES
// Writes Step 2 box only.
// Does NOT generate Location Groups yet.
// ======================================================

function checkFeasibility() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const params = getParametersMap_();

  const parametersSheetName = getParametersSheetName_();
  const cleanedSheetName = getParamSafe_(
    params,
    "CleanedSheet",
    getDefaultCleanedSheetName_()
  );

  const parameterSheet = getRequiredSheet_(ss, parametersSheetName);
  const cleanedSheet = getRequiredSheet_(ss, cleanedSheetName);

  const directorCapacity = getRequiredNumberParam_(params, "DirectorCapacity");
  const heavySceneWeight = getRequiredNumberParam_(params, "HeavySceneWeight");
  const lightSceneWeight = getRequiredNumberParam_(params, "LightSceneWeight");

  if (directorCapacity <= 0) {
    throw new Error("DirectorCapacity must be greater than 0.");
  }

  if (heavySceneWeight <= 0) {
    throw new Error("HeavySceneWeight must be greater than 0.");
  }

  if (lightSceneWeight <= 0) {
    throw new Error("LightSceneWeight must be greater than 0.");
  }

  const cleanedValues = cleanedSheet.getDataRange().getDisplayValues();

  if (cleanedValues.length < 2) {
    throw new Error("CLEANED_SCENES has no scene rows. Run cleanRawScenes first.");
  }

  const headers = cleanedValues[0].map(h => normalizeForMatch_(h));

  const typeCol = findHeaderCol_(headers, [
    "TYPE",
    "SCENETYPE",
    "SCENEWEIGHT",
    "WEIGHT",
    "LIGHTHEAVY",
    "HEAVYLIGHT"
  ]);

  const timeCol = findHeaderCol_(headers, [
    "TIMEOFDAY",
    "TOD",
    "TIME",
    "DAYNIGHT",
    "DAY NIGHT"
  ]);

  if (typeCol === -1) {
    throw new Error("Missing Type / SceneWeight / LightHeavy column in CLEANED_SCENES.");
  }

  if (timeCol === -1) {
    throw new Error("Missing TimeOfDay / TOD / DayNight column in CLEANED_SCENES.");
  }

  let dayLightCount = 0;
  let dayHeavyCount = 0;
  let nightLightCount = 0;
  let nightHeavyCount = 0;

  for (let r = 1; r < cleanedValues.length; r++) {
    const row = cleanedValues[r];

    if (row.every(cell => String(cell || "").trim() === "")) continue;

    const type = normalizeForMatch_(row[typeCol]);
    const timeOfDay = normalizeForMatch_(row[timeCol]);

    const isHeavy = type.includes("HEAVY");
const unitWeight = isHeavy ? heavySceneWeight : lightSceneWeight;

const isDayOnly = timeOfDay === "DAY";
const isNightOnly = timeOfDay === "NIGHT";
const isFlexible = timeOfDay.includes("DAY") && timeOfDay.includes("NIGHT");

if (isDayOnly) {
  if (isHeavy) {
    dayHeavyCount++;
  } else {
    dayLightCount++;
  }
}

else if (isNightOnly) {
  if (isHeavy) {
    nightHeavyCount++;
  } else {
    nightLightCount++;
  }
}

else if (isFlexible) {
  const currentDayUnits =
    (dayLightCount * lightSceneWeight) +
    (dayHeavyCount * heavySceneWeight);

  const currentNightUnits =
    (nightLightCount * lightSceneWeight) +
    (nightHeavyCount * heavySceneWeight);

  // Put flexible scene into the currently lighter bucket
  if (currentDayUnits <= currentNightUnits) {
    if (isHeavy) {
      dayHeavyCount++;
    } else {
      dayLightCount++;
    }
  } else {
    if (isHeavy) {
      nightHeavyCount++;
    } else {
      nightLightCount++;
    }
  }
}
  }

  const totalDayUnits =
    (dayLightCount * lightSceneWeight) +
    (dayHeavyCount * heavySceneWeight);

  const totalNightUnits =
    (nightLightCount * lightSceneWeight) +
    (nightHeavyCount * heavySceneWeight);

  const dayBlockCapacity = directorCapacity * 0.5;
  const nightBlockCapacity = directorCapacity * 0.5;

  const minDaysForDayScenes =
    totalDayUnits > 0 ? Math.ceil(totalDayUnits / dayBlockCapacity) : 0;

  const minDaysForNightScenes =
    totalNightUnits > 0 ? Math.ceil(totalNightUnits / nightBlockCapacity) : 0;

  const recommendedMinDays = Math.max(
    1,
    minDaysForDayScenes,
    minDaysForNightScenes
  );

  writeStep2Box_(parameterSheet, recommendedMinDays);
}


// ======================================================
// WRITE STEP 2 BOX
// Layout:
// D1:E1 = Parameter | Input
// D2:E2 = Minimum Filming Days Required
// D3:E3 = Desired Number of Filming Days
// ======================================================

function writeStep2Box_(sheet, recommendedMinDays) {
  const oldDesiredValue = Number(sheet.getRange("E3").getValue());

  const desiredDays =
    oldDesiredValue && oldDesiredValue >= recommendedMinDays
      ? oldDesiredValue
      : recommendedMinDays;

  // Clear only Step 2 table.
  sheet.getRange("D1:E3").clearContent().clearFormat();

  // Header row
  sheet.getRange("D1:E1").setValues([["Parameter", "Input"]]);
  formatBlackHeader_(sheet.getRange("D1:E1"));

  // Minimum filming days required
  sheet.getRange("D2")
    .setValue("Minimum Filming Days\nRequired")
    .setHorizontalAlignment("center")
    .setVerticalAlignment("middle")
    .setWrap(true);

  sheet.getRange("E2")
    .setValue(recommendedMinDays)
    .setBackground("#d9ead3")
    .setFontWeight("bold")
    .setHorizontalAlignment("center")
    .setVerticalAlignment("middle");

  // Desired filming days
  sheet.getRange("D3")
    .setValue(
      "Desired Number of Filming\nDays (Note: Value must be\ngreater than or equal to the\nminimum number of filming\ndays required)"
    )
    .setHorizontalAlignment("center")
    .setVerticalAlignment("middle")
    .setWrap(true);

  const desiredCell = sheet.getRange("E3");

  desiredCell
    .setValue(desiredDays)
    .setBackground("#e7e6e6")
    .setFontColor("#ff0000")
    .setFontWeight("bold")
    .setHorizontalAlignment("center")
    .setVerticalAlignment("middle");

  const rule = SpreadsheetApp.newDataValidation()
    .requireNumberGreaterThanOrEqualTo(recommendedMinDays)
    .setAllowInvalid(false)
    .setHelpText("Must be greater than or equal to the minimum filming days required.")
    .build();

  desiredCell.setDataValidation(rule);

  sheet.getRange("D1:E3")
    .setBorder(true, true, true, true, true, true);

  sheet.setColumnWidth(4, 260);
  sheet.setColumnWidth(5, 160);
  sheet.setRowHeight(2, 55);
  sheet.setRowHeight(3, 95);
}


