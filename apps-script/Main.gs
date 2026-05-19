// ======================================================
// CONFIG.GS
// Default sheet names — shared across all files.
// ======================================================

const DEFAULT_RAW_SHEET_NAME = "RAW_SCENES";
const DEFAULT_CLEANED_SHEET_NAME = "CLEANED_SCENES";
const DEFAULT_ACTOR_FEES_SHEET_NAME = "ACTOR_FEES";
const DEFAULT_STAFF_FEES_SHEET_NAME = "STAFF_FEES";
const DEFAULT_LOCATION_FEES_SHEET_NAME = "LOCATION_FEES";
const DEFAULT_PARAMETERS_SHEET_NAME = "PARAMETERS";
const DEFAULT_OUTPUT_SHEET_NAME = "OUTPUT";
const DEFAULT_CLUSTERING_OUTPUT_SHEET_NAME = "CLUSTERING_OUTPUT";

// Day-by-day detailed table
const DEFAULT_CLEANED_FOR_COSTS_SHEET_NAME = "CLEANED FOR COSTS";

// Separate summary tab
const DEFAULT_COST_SUMMARY_SHEET_NAME = "PROJECTED_COSTS";

// ======================================================
// MAIN.GS
// Entry points — run these from the Apps Script editor.
// ======================================================

function generateLocation() {
  generateLocationGroups();
}

function runFullClustering() {
  cleanRawScenes();

  runClustering();
  SpreadsheetApp.flush();

  createClusteringOutput();
  SpreadsheetApp.flush();

  // This creates the DAY 1 / DAY 2 detailed table
  createCleanedForCosts();
  SpreadsheetApp.flush();

  // This creates the separate SPECIALIZED_COSTS summary
  createCostSummary();
  SpreadsheetApp.flush();

  autoFitWorkbook_();
}

