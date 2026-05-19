// ======================================================
// HELPERS.GS
// Shared utilities used across cleaning, clustering,
// costs, parameters, and formatting logic.
// ======================================================


// ======================================================
// 1. PARAMETER + SHEET HELPERS
// ======================================================

function getParametersMap_() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName(DEFAULT_PARAMETERS_SHEET_NAME);

  if (!sheet) return {};

  const values = sheet.getDataRange().getDisplayValues();
  const params = {};

  for (let r = 1; r < values.length; r++) {
    const key = String(values[r][0] || "").trim();
    const value = String(values[r][1] || "").trim();

    if (key) params[key] = value;
  }

  return params;
}


function getParam_(params, key, defaultValue) {
  const value = params[key];

  if (value === undefined || value === null || String(value).trim() === "") {
    return defaultValue;
  }

  return String(value).trim();
}


function getParamSafe_(params, key, defaultValue) {
  if (params[key] !== undefined && String(params[key]).trim() !== "") {
    return String(params[key]).trim();
  }

  const target = normalizeForMatch_(key);

  for (const existingKey in params) {
    if (normalizeForMatch_(existingKey) === target) {
      const value = params[existingKey];

      if (value !== undefined && value !== null && String(value).trim() !== "") {
        return String(value).trim();
      }
    }
  }

  return defaultValue;
}


function getRequiredParameter_(params, key) {
  const value = params[key];

  if (!value || String(value).trim() === "") {
    throw new Error("Missing required parameter in PARAMETERS sheet: " + key);
  }

  return String(value).trim();
}


function getRequiredNumberParam_(params, key) {
  const value = getParamSafe_(params, key, "");

  if (value === "") {
    throw new Error("Missing required parameter: " + key);
  }

  const numberValue = Number(String(value).replace(/,/g, "").trim());

  if (isNaN(numberValue)) {
    throw new Error(key + " must be a number.");
  }

  return numberValue;
}


function getRequiredSheet_(ss, sheetName) {
  const sheet = ss.getSheetByName(sheetName);

  if (!sheet) {
    throw new Error("Missing sheet: " + sheetName);
  }

  return sheet;
}


function getParametersSheetName_() {
  if (typeof DEFAULT_PARAMETERS_SHEET_NAME !== "undefined") {
    return DEFAULT_PARAMETERS_SHEET_NAME;
  }

  return "PARAMETERS";
}


function getDefaultCleanedSheetName_() {
  if (typeof DEFAULT_CLEANED_SHEET_NAME !== "undefined") {
    return DEFAULT_CLEANED_SHEET_NAME;
  }

  return "CLEANED_SCENES";
}


// ======================================================
// 2. STEP 2 / MAXDAYS SYNC HELPER
// ======================================================

function syncMaxDaysFromStep2_() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const parameterSheet = getRequiredSheet_(ss, DEFAULT_PARAMETERS_SHEET_NAME);

  const desiredDays = Number(parameterSheet.getRange("E3").getValue());

  if (!desiredDays || desiredDays < 1) {
    throw new Error("Desired Number of Filming Days in E3 must be at least 1.");
  }

  const values = parameterSheet.getDataRange().getValues();

  let maxDaysRow = -1;

  for (let r = 0; r < values.length; r++) {
    const key = String(values[r][0] || "").trim();

    if (key === "MaxDays") {
      maxDaysRow = r + 1;
      break;
    }
  }

  if (maxDaysRow !== -1) {
    parameterSheet.getRange(maxDaysRow, 2).setValue(desiredDays);
  } else {
    const newRow = parameterSheet.getLastRow() + 1;
    parameterSheet.getRange(newRow, 1).setValue("MaxDays");
    parameterSheet.getRange(newRow, 2).setValue(desiredDays);
  }
}


// ======================================================
// 3. FEE + NAME HELPERS
// ======================================================

function getActorNamesFromFeesSheet_(actorFeesSheetName) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const feesSheet = ss.getSheetByName(actorFeesSheetName);

  if (!feesSheet) return [];

  const lastRow = feesSheet.getLastRow();
  if (lastRow < 2) return [];

  return feesSheet
    .getRange(2, 1, lastRow - 1, 1)
    .getDisplayValues()
    .map(row => String(row[0] || "").trim())
    .filter(name => name);
}


function getSpecificDayStaffNamesFromFeesSheet_(staffFeesSheetName) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const staffSheet = ss.getSheetByName(staffFeesSheetName);

  if (!staffSheet) return [];

  const lastRow = staffSheet.getLastRow();
  if (lastRow < 2) return [];

  const lastCol = staffSheet.getLastColumn();

  const headers = staffSheet
    .getRange(1, 1, 1, lastCol)
    .getDisplayValues()[0];

  const normalizedHeaders = headers.map(h => normalizeForMatch_(h));

  const staffCol = normalizedHeaders.findIndex(h =>
    h === "STAFF" ||
    h === "STAFFNAME" ||
    h === "STAFFGROUP" ||
    h === "STAFFTYPE" ||
    h === "CREW" ||
    h === "NAME"
  );

  const specificCol = normalizedHeaders.findIndex(h => {
  const compact = h.replace(/\s+/g, "");

  return (
    compact === "ONLYINSPECIFICDAYS" ||
    compact === "ONLYSPECIFICDAYS" ||
    compact === "SPECIFICDAYS" ||
    compact === "SPECIFICDAY"
  );
});

  if (staffCol === -1) {
    throw new Error(
      "Missing Staff column in " +
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

  const data = staffSheet
    .getRange(2, 1, lastRow - 1, lastCol)
    .getValues();

  return data
    .filter(row => {
      const staffName = String(row[staffCol] || "").trim();
      const onlySpecificDays = row[specificCol] === true || isChecked_(row[specificCol]);

      return staffName && onlySpecificDays;
    })
    .map(row => String(row[staffCol] || "").trim());
}


function getOfficialLocations_(locationFeesSheetName) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName(locationFeesSheetName);

  if (!sheet) return [];

  const lastRow = sheet.getLastRow();
  if (lastRow < 2) return [];

  const lastCol = sheet.getLastColumn();

  const headers = sheet
    .getRange(1, 1, 1, lastCol)
    .getDisplayValues()[0]
    .map(h => normalizeForMatch_(h));

  const locationCol = headers.findIndex(h =>
    h === "LOCATION" ||
    h === "LOC" ||
    h === "LOCATIONNAME" ||
    h === "NAME"
  );

  const col = locationCol === -1 ? 0 : locationCol;

  return sheet
    .getRange(2, col + 1, lastRow - 1, 1)
    .getDisplayValues()
    .map(row => String(row[0] || "").trim())
    .filter(name => name);
}


function getFeeMap_(sheetName, nameHeaderCandidates) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName(sheetName);

  if (!sheet) return {};

  const lastRow = sheet.getLastRow();
  const lastCol = sheet.getLastColumn();

  if (lastRow < 2 || lastCol < 1) return {};

  const normalizedHeaders = sheet
    .getRange(1, 1, 1, lastCol)
    .getDisplayValues()[0]
    .map(h => normalizeForMatch_(h));

  let nameCol = normalizedHeaders.findIndex(h => nameHeaderCandidates.includes(h));
  if (nameCol === -1) nameCol = 0;

  let costCol = normalizedHeaders.findIndex(h => isCostLikeHeader_(h));
  if (costCol === -1) costCol = 1;

  const map = {};

  sheet
    .getRange(2, 1, lastRow - 1, lastCol)
    .getDisplayValues()
    .forEach(row => {
      const name = cleanCell_(row[nameCol]);
      const fee = cleanCell_(row[costCol]);

      if (name) {
        map[normalizeForMatch_(name)] = fee;
      }
    });

  return map;
}


function getFeeMapAsNumber_(sheetName, nameHeaderCandidates) {
  const rawMap = getFeeMap_(sheetName, nameHeaderCandidates);
  const numberMap = {};

  Object.keys(rawMap).forEach(key => {
    numberMap[key] = parseMoneyNumber_(rawMap[key]);
  });

  return numberMap;
}


function getFeeForName_(name, feeMap) {
  const key = normalizeForMatch_(name);

  if (feeMap[key] !== undefined) {
    return feeMap[key];
  }

  return "";
}


function getFeeForNameAsNumber_(name, feeMap) {
  const key = normalizeForMatch_(name);

  if (feeMap[key] !== undefined) {
    return parseMoneyNumber_(feeMap[key]);
  }

  return 0;
}


// ======================================================
// 4. MONEY + API PAYLOAD HELPERS
// ======================================================

function parseMoneyNumber_(value) {
  if (value === null || value === undefined || value === "") return 0;

  if (typeof value === "number") return value;

  const cleaned = String(value)
    .replace(/[₱$]/g, "")
    .replace(/,/g, "")
    .replace(/\s+/g, "")
    .trim();

  return Number(cleaned) || 0;
}


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


// ======================================================
// 5. HEADER DETECTION HELPERS
// ======================================================

function findHeaderRowIndex_(data) {
  for (let r = 0; r < data.length; r++) {
    const row = data[r].map(v => normalizeForMatch_(v));

    const hasSeq = row.some(v => [
      "SEQ",
      "SEQNO",
      "SEQNUM",
      "SEQUENCE"
    ].includes(v));

    const hasTod = row.some(v => [
      "TOD",
      "TIMEOFDAY",
      "TIME",
      "DAYNIGHT"
    ].includes(v));

    const hasLocation = row.some(v => [
      "LOCATION",
      "LOC"
    ].includes(v));

    if (hasSeq && hasTod && hasLocation) {
      return r;
    }
  }

  return -1;
}


function buildEffectiveHeaders_(data, headerRowIndex) {
  const topRow = data[headerRowIndex] || [];
  const belowRow = data[headerRowIndex + 1] || [];

  const maxCols = Math.max(topRow.length, belowRow.length);
  const headers = [];

  const groupedHeaders = [
    "CHARACTERS",
    "CAST",
    "ACTORS",
    "STAFF",
    "TALENTS"
  ];

  for (let c = 0; c < maxCols; c++) {
    const top = String(topRow[c] || "").trim();
    const below = String(belowRow[c] || "").trim();

    const topNorm = normalizeForMatch_(top);
    const belowNorm = normalizeForMatch_(below);

    if (groupedHeaders.includes(topNorm) && belowNorm) {
      headers.push(below);
    } else if (!topNorm && belowNorm) {
      headers.push(below);
    } else {
      headers.push(top);
    }
  }

  return headers;
}


function getFirstDataRowIndex_(data, headerRowIndex) {
  const nextRow = data[headerRowIndex + 1] || [];
  const firstCell = String(nextRow[0] || "").trim();

  return isSceneId_(firstCell) ? headerRowIndex + 1 : headerRowIndex + 2;
}


function findHeaderCol_(upperHeaders, candidates) {
  const normalizedCandidates = candidates.map(c => normalizeForMatch_(c));

  for (let i = 0; i < upperHeaders.length; i++) {
    const header = normalizeForMatch_(upperHeaders[i]);

    if (normalizedCandidates.includes(header)) {
      return i;
    }
  }

  return -1;
}


function findBestHeaderIndex_(headers, targetName) {
  const target = normalizeForMatch_(targetName);

  for (let i = 0; i < headers.length; i++) {
    if (normalizeForMatch_(headers[i]) === target) {
      return i;
    }
  }

  for (let i = 0; i < headers.length; i++) {
    const header = normalizeForMatch_(headers[i]);

    if (header && target && (header.includes(target) || target.includes(header))) {
      return i;
    }
  }

  const targetWords = target
    .split(" ")
    .filter(w => w.length > 2);

  for (let i = 0; i < headers.length; i++) {
    const header = normalizeForMatch_(headers[i]);

    if (targetWords.length > 0 && targetWords.every(w => header.includes(w))) {
      return i;
    }
  }

  return -1;
}


// ======================================================
// 6. CLEANING + PARSING HELPERS
// ======================================================

function parseTimeOfDay_(value) {
  const raw = String(value || "").toUpperCase().trim();
  if (!raw) return "";

  if (raw.includes("I")) return "DAY AND NIGHT";

  const hasD = raw.includes("D");
  const hasN = raw.includes("N");

  if (hasD && hasN) return "DAY AND NIGHT";
  if (hasD) return "DAY";
  if (hasN) return "NIGHT";

  return "";
}


function splitLocation_(value, officialLocations) {
  const raw = String(value || "")
    .replace(/\s+/g, " ")
    .trim();

  if (!raw) {
    return {
      broadLocation: "",
      locationDetail: ""
    };
  }

  const parsed = parseLocationParts_(raw);
  const broadLocation = cleanLocationName_(parsed.base, officialLocations);

  return {
    broadLocation: broadLocation,
    locationDetail: parsed.detail
      ? broadLocation + ": " + parsed.detail
      : broadLocation
  };
}


function parseLocationParts_(rawLocation) {
  const raw = String(rawLocation || "")
    .replace(/\s+/g, " ")
    .trim();

  const match = raw.match(/[:：\-–—*]/);

  if (!match) {
    return {
      base: raw,
      detail: ""
    };
  }

  return {
    base: raw.slice(0, match.index).replace(/\s+/g, " ").trim(),
    detail: raw.slice(match.index + 1).replace(/\s+/g, " ").trim()
  };
}


function cleanLocationName_(value, officialLocations) {
  const original = String(value || "")
    .replace(/\s+/g, " ")
    .trim();

  const matchKey = normalizeForMatch_(original);

  if (officialLocations && officialLocations.length > 0) {
    for (const loc of officialLocations) {
      if (normalizeForMatch_(loc) === matchKey) {
        return String(loc).trim().toUpperCase();
      }
    }

    for (const loc of officialLocations) {
      const locKey = normalizeForMatch_(loc);

      if (matchKey.includes(locKey) || locKey.includes(matchKey)) {
        return String(loc).trim().toUpperCase();
      }
    }

    let bestLocation = "";
    let bestScore = 0;

    officialLocations.forEach(loc => {
      const score = similarityScore_(matchKey, normalizeForMatch_(loc));

      if (score > bestScore) {
        bestScore = score;
        bestLocation = loc;
      }
    });

    if (bestLocation && bestScore >= 0.75) {
      return String(bestLocation).trim().toUpperCase();
    }
  }

  return original.toUpperCase();
}


function similarityScore_(a, b) {
  const s1 = String(a || "");
  const s2 = String(b || "");

  if (!s1 || !s2) return 0;
  if (s1 === s2) return 1;

  return 1 - levenshteinDistance_(s1, s2) / Math.max(s1.length, s2.length);
}


function levenshteinDistance_(a, b) {
  const s1 = String(a || "");
  const s2 = String(b || "");

  const dp = Array.from({ length: s1.length + 1 }, () =>
    Array(s2.length + 1).fill(0)
  );

  for (let i = 0; i <= s1.length; i++) dp[i][0] = i;
  for (let j = 0; j <= s2.length; j++) dp[0][j] = j;

  for (let i = 1; i <= s1.length; i++) {
    for (let j = 1; j <= s2.length; j++) {
      const cost = s1[i - 1] === s2[j - 1] ? 0 : 1;

      dp[i][j] = Math.min(
        dp[i - 1][j] + 1,
        dp[i][j - 1] + 1,
        dp[i - 1][j - 1] + cost
      );
    }
  }

  return dp[s1.length][s2.length];
}


// ======================================================
// 7. BASIC UTILITY HELPERS
// ======================================================

function isChecked_(value) {
  const v = String(value || "").trim().toUpperCase();

  return [
    "TRUE",
    "YES",
    "Y",
    "1",
    "✓",
    "✔",
    "CHECK",
    "CHECKED",
    "X"
  ].includes(v);
}


function isCheckedOrFilled_(value) {
  const v = String(value || "").trim();

  if (!v) return false;

  return ![
    "FALSE",
    "NO",
    "N",
    "0",
    "UNCHECKED"
  ].includes(v.toUpperCase());
}


function isSceneId_(value) {
  const v = String(value || "").trim();

  if (!v) return false;

  return (
    /^[0-9]+[A-Z]?$/i.test(v) ||
    /^[0-9]+[A-Z]?\s*\/\s*[0-9A-Z]+$/i.test(v) ||
    /^[0-9]+[A-Z]?\s*,\s*[0-9A-Z]+$/i.test(v)
  );
}


function normalizeForMatch_(value) {
  return String(value || "")
    .toUpperCase()
    .replace(/['‘’]/g, "")
    .replace(/[^A-Z0-9 ]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}


function normalizeSceneKey_(value) {
  return String(value || "")
    .toUpperCase()
    .replace(/\s+/g, "")
    .replace(/，/g, ",")
    .replace(/／/g, "/")
    .replace(/–|—/g, "-")
    .trim();
}


function cleanCell_(value) {
  return String(value || "")
    .replace(/\s+/g, " ")
    .replace(/\s*,\s*/g, ", ")
    .replace(/\s*\/\s*/g, " / ")
    .replace(/\s*:\s*/g, ": ")
    .trim();
}


function splitCommaNames_(value) {
  return String(value || "")
    .split(",")
    .map(item => cleanCell_(item))
    .filter(item => item);
}


function escapeRegex_(value) {
  return String(value || "").replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}


// ======================================================
// 8. CLEANED FOR COSTS / DAY BLOCK HELPERS
// ======================================================

function findSpecializedCostDayBlocks_(values) {
  const blocks = [];

  for (let r = 0; r < Math.min(values.length, 10); r++) {
    const row = values[r];

    for (let c = 0; c < row.length; c++) {
      const cell = cleanCell_(row[c]);
      const norm = normalizeForMatch_(cell);

      if (!/^DAY [0-9]+$/.test(norm)) continue;

      const headerRow = r + 1;
      if (headerRow >= values.length) continue;

      const headers = values[headerRow].map(h => normalizeForMatch_(h));

      const locationCol = findHeaderInWindow_(headers, c, ["LOCATION", "LOC"]);
      const actorCol = findHeaderInWindow_(headers, c, ["ACTOR", "ACTORS", "CAST"]);
      const staffCol = findHeaderInWindow_(headers, c, ["STAFF", "STAFFNEEDED", "CREW"]);

      if (locationCol === -1 || actorCol === -1 || staffCol === -1) continue;

      blocks.push({
        dayLabel: norm,
        dayCol: c,
        headerRow: headerRow,
        locationCol: locationCol,
        locationCostCol: locationCol + 1,
        actorCol: actorCol,
        actorCostCol: actorCol + 1,
        staffCol: staffCol,
        staffCostCol: staffCol + 1
      });
    }
  }

  return blocks;
}


function findHeaderInWindow_(headers, startCol, candidates) {
  const endCol = Math.min(headers.length, startCol + 7);

  for (let c = startCol; c < endCol; c++) {
    if (candidates.includes(headers[c])) {
      return c;
    }
  }

  return -1;
}


