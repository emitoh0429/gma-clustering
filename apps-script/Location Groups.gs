// ======================================================
// GENERATE LOCATION GROUPS
// Button should be assigned to: generateLocationGroups
// Creates LocationGroup boxes starting at D8
// Number of input rows is based on locations in LOCATION_FEES
// ======================================================

function generateLocationGroups() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();

  const parameterSheet = getRequiredSheet_(ss, DEFAULT_PARAMETERS_SHEET_NAME);
  const locationFeesSheet = getRequiredSheet_(ss, DEFAULT_LOCATION_FEES_SHEET_NAME);

  const locationFeesValues = locationFeesSheet.getDataRange().getDisplayValues();

  if (locationFeesValues.length < 2) {
    throw new Error("LOCATION_FEES has no location rows.");
  }

  const headers = locationFeesValues[0].map(h => normalizeForMatch_(h));

  const locationCol = findHeaderCol_(headers, [
    "LOCATION",
    "LOC"
  ]);

  if (locationCol === -1) {
    throw new Error("Missing Location column in LOCATION_FEES.");
  }

  const uniqueLocations = [];

  for (let r = 1; r < locationFeesValues.length; r++) {
    const location = String(locationFeesValues[r][locationCol] || "").trim();

    if (location && !uniqueLocations.includes(location)) {
      uniqueLocations.push(location);
    }
  }

  uniqueLocations.sort();

  writeLocationGroupBoxes_(parameterSheet, uniqueLocations.length, uniqueLocations);

  ss.toast(
    "Generated " + uniqueLocations.length + " LocationGroup boxes based on LOCATION_FEES.",
    "Location Groups",
    5
  );
}


// ======================================================
// WRITE LOCATION GROUP BOXES
// ======================================================

function writeLocationGroupBoxes_(sheet, numberOfGroups, uniqueLocations) {
  const startRow = 8;
  const startCol = 4; // D

  const blockWidth = 2;
  const spacerWidth = 1;
  const groupsPerRow = 3;

  const locationCount = Math.max(uniqueLocations.length, 1);
  const totalRows = locationCount + 1; // header + input rows
  const rowSpacer = 2;

  // Clear old LocationGroup area
  sheet.getRange("D8:AZ300")
    .clearContent()
    .clearFormat()
    .clearDataValidations()
    .breakApart();

  for (let g = 1; g <= numberOfGroups; g++) {
    const groupIndex = g - 1;

    const rowBlock = Math.floor(groupIndex / groupsPerRow);
    const colBlock = groupIndex % groupsPerRow;

    const row = startRow + rowBlock * (totalRows + rowSpacer);
    const col = startCol + colBlock * (blockWidth + spacerWidth);

    // Header
    sheet.getRange(row, col, 1, 2)
      .setValues([["Parameter", "Input"]]);

    formatBlackHeader_(sheet.getRange(row, col, 1, 2));

    // LocationGroup label
    sheet.getRange(row + 1, col)
      .setValue("LocationGroup" + g)
      .setHorizontalAlignment("center")
      .setVerticalAlignment("middle")
      .setWrap(true);

    // Input cells
    const inputRange = sheet.getRange(row + 1, col + 1, locationCount, 1);

    inputRange
      .clearContent()
      .setFontColor("#ff0000")
      .setHorizontalAlignment("left")
      .setVerticalAlignment("middle")
      .setWrap(true);

    // Dropdown
    if (uniqueLocations.length > 0) {
      const rule = SpreadsheetApp.newDataValidation()
        .requireValueInList(uniqueLocations, true)
        .setAllowInvalid(true)
        .setHelpText("Assign each LOCATION_FEES location to a LocationGroup.")
        .build();

      inputRange.setDataValidation(rule);
    }

    // Borders
    sheet.getRange(row, col, totalRows, 2)
      .setBorder(true, true, true, true, true, true);

    // Column widths
    sheet.setColumnWidth(col, 170);
    sheet.setColumnWidth(col + 1, 160);

    // Spacer column
    const spacerCol = col + 2;

    sheet.setColumnWidth(spacerCol, 40);

    sheet.getRange(row, spacerCol, totalRows, 1)
      .clearContent()
      .clearFormat()
      .clearDataValidations()
      .setBorder(false, false, false, false, false, false);
  }
}


// ======================================================
// READ LOCATION GROUPS FOR PAYLOAD
// Reads from the SAME area where boxes are written: D8 onward
// ======================================================

function readLocationGroups_() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName(DEFAULT_PARAMETERS_SHEET_NAME);

  if (!sheet) {
    throw new Error("Missing sheet: " + DEFAULT_PARAMETERS_SHEET_NAME);
  }

  const startRow = 8;
  const startCol = 4; // D

  const blockWidth = 2;
  const spacerWidth = 1;

  const groupsPerRow = 3;
  const maxGroupsToRead = 30;

  const locationCount = Math.max(
    getOfficialLocations_(DEFAULT_LOCATION_FEES_SHEET_NAME).length,
    1
  );

  const totalRows = locationCount + 1; // header + input rows
  const rowSpacer = 2;

  const locationGroups = [];

  for (let g = 1; g <= maxGroupsToRead; g++) {
    const groupIndex = g - 1;

    const rowBlock = Math.floor(groupIndex / groupsPerRow);
    const colBlock = groupIndex % groupsPerRow;

    const row = startRow + rowBlock * (totalRows + rowSpacer);
    const col = startCol + colBlock * (blockWidth + spacerWidth);

    const groupName = String(
      sheet.getRange(row + 1, col).getDisplayValue() || ""
    ).trim();

    if (!groupName || !groupName.startsWith("LocationGroup")) {
      continue;
    }

    const inputCol = col + 1;

    const locations = sheet
      .getRange(row + 1, inputCol, locationCount, 1)
      .getDisplayValues()
      .flat()
      .map(v => String(v || "").trim())
      .filter(v => v !== "");

    if (locations.length > 0) {
      locationGroups.push([groupName, ...locations]);
    }
  }

  return locationGroups;
}


// ======================================================
// VALIDATE ALL LOCATIONS ARE ASSIGNED TO LOCATION GROUPS
// Checks LOCATION_FEES against filled LocationGroup inputs
// Use this before sending payload to Python
// ======================================================

function validateAllLocationsAssignedToGroups_() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();

  const parameterSheet = getRequiredSheet_(ss, DEFAULT_PARAMETERS_SHEET_NAME);
  const locationFeesSheet = getRequiredSheet_(ss, DEFAULT_LOCATION_FEES_SHEET_NAME);
  const values = locationFeesSheet.getDataRange().getDisplayValues();

  clearLocationGroupValidationMessage_(parameterSheet);

  if (values.length < 2) {
    writeLocationGroupValidationMessage_(
      parameterSheet,
      "ERROR",
      "LOCATION_FEES has no location rows."
    );

    throw new Error("LOCATION_FEES has no location rows.");
  }

  const headers = values[0].map(h => normalizeForMatch_(h));

  const locationCol = findHeaderCol_(headers, [
    "LOCATION",
    "LOC"
  ]);

  if (locationCol === -1) {
    writeLocationGroupValidationMessage_(
      parameterSheet,
      "ERROR",
      "Missing Location column in LOCATION_FEES."
    );

    throw new Error("Missing Location column in LOCATION_FEES.");
  }

  // All required locations from LOCATION_FEES
  const requiredLocations = [];

  for (let r = 1; r < values.length; r++) {
    const location = String(values[r][locationCol] || "").trim();

    if (location && !requiredLocations.includes(location)) {
      requiredLocations.push(location);
    }
  }

  // Locations already assigned in LocationGroups
  const locationGroups = readLocationGroups_();

  const assignedLocations = [];

  locationGroups.forEach(group => {
    const locationsOnly = group.slice(1);

    locationsOnly.forEach(location => {
      const cleanLocation = String(location || "").trim();

      if (cleanLocation && !assignedLocations.includes(cleanLocation)) {
        assignedLocations.push(cleanLocation);
      }
    });
  });

  // Find missing locations
  const missingLocations = requiredLocations.filter(location => {
    return !assignedLocations.includes(location);
  });

  if (missingLocations.length > 0) {
    const message =
      "These locations have not been added to any LocationGroup yet:\n\n" +
      missingLocations.join(", ") +
      "\n\nPlease add them before running clustering.";

    writeLocationGroupValidationMessage_(
      parameterSheet,
      "ERROR",
      message
    );

    throw new Error(message);
  }

  writeLocationGroupValidationMessage_(
    parameterSheet,
    "OK",
    "All LOCATION_FEES locations have been assigned to a LocationGroup."
  );

  return true;
}


// ======================================================
// LOCATION GROUP VALIDATION MESSAGE BOX
// Smaller layout so it does not look awkward / oversized.
// ======================================================

function clearLocationGroupValidationMessage_(sheet) {
  sheet.getRange("D4:H6")
    .clearContent()
    .clearFormat()
    .clearDataValidations()
    .breakApart();
}


function writeLocationGroupValidationMessage_(sheet, status, message) {
  clearLocationGroupValidationMessage_(sheet);

  const titleRange = sheet.getRange("D4:H4");
  const messageRange = sheet.getRange("D5:H6");

  titleRange
    .merge()
    .setValue("LocationGroup Check")
    .setFontWeight("bold")
    .setFontSize(11)
    .setHorizontalAlignment("center")
    .setVerticalAlignment("middle")
    .setWrap(true);

  messageRange
    .merge()
    .setValue(message)
    .setFontSize(9)
    .setWrap(true)
    .setHorizontalAlignment("left")
    .setVerticalAlignment("top");

  sheet.getRange("D4:H6")
    .setBorder(true, true, true, true, true, true);

  if (status === "OK") {
    sheet.getRange("D4:H6").setBackground("#d9ead3");
  } else {
    sheet.getRange("D4:H6").setBackground("#f4cccc");
  }

  sheet.setRowHeight(4, 30);
  sheet.setRowHeight(5, 55);
  sheet.setRowHeight(6, 55);

  for (let col = 4; col <= 10; col++) {
    sheet.setColumnWidth(col, 120);
  }
}
