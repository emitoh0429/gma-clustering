// ======================================================
// FORMATTING.GS
// All sheet formatting and autofit helpers.
// ======================================================
 
function formatBlackHeader_(range) {
  range
    .setBackground("#000000")
    .setFontColor("#ffffff")
    .setFontWeight("bold")
    .setHorizontalAlignment("center")
    .setVerticalAlignment("middle")
    .setWrap(true);
}
 
 
function formatCleanedScenesSheet_(sheet, numRows, numCols) {
  if (numRows < 1 || numCols < 1) return;
 
  sheet.setFrozenRows(0);
 
  sheet.getRange(1, 1, numRows, numCols)
    .setVerticalAlignment("middle")
    .setWrap(true)
    .setBorder(true, true, true, true, true, true);
 
  sheet.getRange(1, 1, 1, numCols)
    .setHorizontalAlignment("center")
    .setVerticalAlignment("middle")
    .setWrap(true);
 
  if (numRows > 1) {
    sheet.getRange(2, 1, numRows - 1, numCols).setVerticalAlignment("middle").setWrap(true);
    sheet.getRange(2, 1, numRows - 1, 3).setHorizontalAlignment("center");
    sheet.getRange(2, 4, numRows - 1, numCols - 3).setHorizontalAlignment("left");
  }
 
  SpreadsheetApp.flush();
  sheet.autoResizeColumns(1, numCols);
  sheet.autoResizeRows(1, numRows);
 
  if (numCols >= 1) sheet.setColumnWidth(1, Math.max(sheet.getColumnWidth(1), 110));
  if (numCols >= 2) sheet.setColumnWidth(2, Math.max(sheet.getColumnWidth(2), 110));
  if (numCols >= 3) sheet.setColumnWidth(3, Math.max(sheet.getColumnWidth(3), 150));
  if (numCols >= 4) sheet.setColumnWidth(4, Math.max(sheet.getColumnWidth(4), 170));
  if (numCols >= 5) sheet.setColumnWidth(5, Math.max(sheet.getColumnWidth(5), 300));
  if (numCols >= 6) sheet.setColumnWidth(6, Math.max(sheet.getColumnWidth(6), 450));
  if (numCols >= 7) sheet.setColumnWidth(7, Math.max(sheet.getColumnWidth(7), 330));
  if (numCols >= 8) sheet.setColumnWidth(8, Math.max(sheet.getColumnWidth(8), 500));
}
 
 
function formatClusteringOutputSheet_(sheet, numRows, numCols) {
  if (numRows < 1 || numCols < 1) return;
 
  sheet.setFrozenRows(0);
 
  sheet.getRange(1, 1, numRows, numCols)
    .setVerticalAlignment("middle")
    .setWrap(true)
    .setBorder(true, true, true, true, true, true);
 
  formatBlackHeader_(sheet.getRange(1, 1, 1, numCols));
 
  for (let r = 2; r <= numRows; r++) {
    const firstCell = normalizeForMatch_(sheet.getRange(r, 1).getDisplayValue());
    if (firstCell.startsWith("DAY")) {
      sheet.getRange(r, 1, 1, numCols)
        .setBackground("#d9d9d9")
        .setFontWeight("bold")
        .setHorizontalAlignment("left");
    }
  }
 
  if (numRows > 1) {
    sheet.getRange(2, 1, numRows - 1, 3).setHorizontalAlignment("center");
    sheet.getRange(2, 4, numRows - 1, numCols - 3).setHorizontalAlignment("left");
  }
 
  SpreadsheetApp.flush();
  sheet.autoResizeColumns(1, numCols);
  sheet.autoResizeRows(1, numRows);
 
  if (numCols >= 1) sheet.setColumnWidth(1, Math.max(sheet.getColumnWidth(1), 110));
  if (numCols >= 2) sheet.setColumnWidth(2, Math.max(sheet.getColumnWidth(2), 110));
  if (numCols >= 3) sheet.setColumnWidth(3, Math.max(sheet.getColumnWidth(3), 150));
  if (numCols >= 4) sheet.setColumnWidth(4, Math.max(sheet.getColumnWidth(4), 170));
  if (numCols >= 5) sheet.setColumnWidth(5, Math.max(sheet.getColumnWidth(5), 300));
  if (numCols >= 6) sheet.setColumnWidth(6, Math.max(sheet.getColumnWidth(6), 450));
  if (numCols >= 7) sheet.setColumnWidth(7, Math.max(sheet.getColumnWidth(7), 330));
  if (numCols >= 8) sheet.setColumnWidth(8, Math.max(sheet.getColumnWidth(8), 500));
}
 
 
function formatProjectedCostSheet_(sheet, numRows, numCols) {
  if (numRows < 1 || numCols < 1) return;

  sheet.setFrozenRows(0);

  sheet.getRange(1, 1, numRows, numCols)
    .setVerticalAlignment("middle")
    .setHorizontalAlignment("center")
    .setWrap(true)
    .setBorder(true, true, true, true, true, true);

  sheet.getRange(1, 1, 1, numCols)
    .mergeAcross()
    .setBackground("#000000")
    .setFontColor("#ffffff")
    .setFontWeight("bold")
    .setHorizontalAlignment("center")
    .setVerticalAlignment("middle");

  sheet.getRange(2, 1, 1, numCols)
    .setBackground("#d9d9d9")
    .setFontWeight("bold")
    .setHorizontalAlignment("center")
    .setVerticalAlignment("middle");

  // TOTAL/AREA — second to last row
  if (numRows >= 3) {
    sheet.getRange(numRows - 1, 1, 1, numCols)
      .setFontWeight("bold")
      .setBackground("#eeeeee");
  }

  // TOTAL COST — last row
  if (numRows >= 2) {
    sheet.getRange(numRows, 1, 1, numCols)
      .setFontWeight("bold")
      .setBackground("#d9ead3");
  }

  // Format all cost columns, B to last column
  if (numRows > 3 && numCols > 1) {
    sheet.getRange(3, 2, numRows - 3, numCols - 1)
      .setNumberFormat("#,##0");
  }

  SpreadsheetApp.flush();

  sheet.autoResizeColumns(1, numCols);
  sheet.autoResizeRows(1, numRows);

  sheet.setColumnWidth(1, 130);
  sheet.setColumnWidth(2, 130);
  sheet.setColumnWidth(3, 130);
  sheet.setColumnWidth(4, 170);
  sheet.setColumnWidth(5, 150);
}
 
 
// Kept for backwards compatibility
function formatCostSummarySheet_(sheet, numRows, numCols, blockWidth) {
  formatProjectedCostSheet_(sheet, numRows, numCols);
}
 
 
function autoFitWorkbook_() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
 
  const sheetsToSkip = [
    DEFAULT_RAW_SHEET_NAME,
    DEFAULT_ACTOR_FEES_SHEET_NAME,
    DEFAULT_STAFF_FEES_SHEET_NAME,
    DEFAULT_LOCATION_FEES_SHEET_NAME,
    DEFAULT_COST_SUMMARY_SHEET_NAME,
    "RAW_SCENES", "ACTOR_FEES", "STAFF_FEES", "LOCATION_FEES","COST INPUTS",
    , "Read Me!"
  ];
 
  ss.getSheets().forEach(sheet => {
    if (!sheetsToSkip.includes(sheet.getName())) autoFitSheet_(sheet);
  });
}
 
 
function autoFitSheet_(sheet) {
  if (!sheet) return;
 
  const lastRow = sheet.getLastRow();
  const lastCol = sheet.getLastColumn();
  if (lastRow < 1 || lastCol < 1) return;
 
  sheet.getRange(1, 1, lastRow, lastCol)
    .setWrap(true)
    .setVerticalAlignment("middle")
    .setHorizontalAlignment("center");
 
  SpreadsheetApp.flush();
  sheet.autoResizeColumns(1, lastCol);
  sheet.autoResizeRows(1, lastRow);
 
  for (let c = 1; c <= lastCol; c++) {
    if (sheet.getColumnWidth(c) < 100) sheet.setColumnWidth(c, 100);
  }
}
 
 
function autoFitOutputSheet_(sheet) {
  if (!sheet) return;
 
  const lastRow = sheet.getLastRow();
  const lastCol = sheet.getLastColumn();
  if (lastRow < 1 || lastCol < 1) return;
 
  sheet.getRange(1, 1, lastRow, lastCol)
    .setWrap(false)
    .setVerticalAlignment("middle")
    .setHorizontalAlignment("center");
 
  SpreadsheetApp.flush();
  sheet.autoResizeColumns(1, lastCol);
  sheet.autoResizeRows(1, lastRow);
 
  if (lastCol >= 1) sheet.setColumnWidth(1, Math.max(sheet.getColumnWidth(1), 100));
 
  for (let c = 2; c <= lastCol; c++) {
    if (sheet.getColumnWidth(c) < 75) sheet.setColumnWidth(c, 75);
  }
}
 
 
function writeErrorToSheet_(ss, outputSheetName, title, details) {
  let outputSheet = ss.getSheetByName(outputSheetName);
  if (!outputSheet) outputSheet = ss.insertSheet(outputSheetName);
 
  outputSheet.clearContents();
  outputSheet.clearFormats();
  outputSheet.getRange(1, 1).setValue(title);
  outputSheet.getRange(2, 1).setValue(details);
 
  autoFitOutputSheet_(outputSheet);
}

function formatCleanedForCostsSheet_(sheet, numRows, numCols, dayCount) {
  sheet.setFrozenRows(0);

  // Base formatting (no borders here — we'll do it per block)
  sheet.getRange(1, 1, numRows, numCols)
    .setHorizontalAlignment("center")
    .setVerticalAlignment("middle")
    .setWrap(true)
    .setFontFamily("Arial")
    .setFontSize(10);

  const blockWidth = 6;
  const spacerWidth = 1;

  for (let d = 0; d < dayCount; d++) {
    const startCol = d * (blockWidth + spacerWidth) + 1;

    // ✅ Apply borders ONLY to the data block (not the spacer)
    sheet.getRange(1, startCol, numRows, blockWidth)
      .setBorder(true, true, true, true, true, true);

    // DAY header: black
    sheet.getRange(1, startCol, 1, blockWidth)
      .merge()
      .setBackground("#000000")
      .setFontColor("#ffffff")
      .setFontWeight("bold")
      .setFontSize(11);

    // Column header: gray
    sheet.getRange(2, startCol, 1, blockWidth)
      .setBackground("#d9d9d9")
      .setFontColor("#000000")
      .setFontWeight("bold");

    // Body
    sheet.getRange(3, startCol, Math.max(numRows - 2, 1), blockWidth)
      .setBackground(null)
      .setFontColor("#000000");

    // Number formats
    sheet.getRange(3, startCol + 1, Math.max(numRows - 2, 1), 1).setNumberFormat("#,##0");
    sheet.getRange(3, startCol + 3, Math.max(numRows - 2, 1), 1).setNumberFormat("#,##0");
    sheet.getRange(3, startCol + 5, Math.max(numRows - 2, 1), 1).setNumberFormat("#,##0");

    // Column widths
    sheet.setColumnWidth(startCol,     150);
    sheet.setColumnWidth(startCol + 1,  80);
    sheet.setColumnWidth(startCol + 2, 150);
    sheet.setColumnWidth(startCol + 3,  80);
    sheet.setColumnWidth(startCol + 4, 150);
    sheet.setColumnWidth(startCol + 5,  80);

    // Spacer column — clear it completely, no borders
    if (d < dayCount - 1) {
      const spacerCol = startCol + blockWidth;
      sheet.setColumnWidth(spacerCol, 20);
      sheet.getRange(1, spacerCol, numRows, 1)
        .setBackground("#ffffff") // ✅ white instead of null
        .setFontColor("#ffffff")
        .setBorder(false, false, false, false, false, false);
    }
  }
}
