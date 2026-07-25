import logging
import os
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple
import pandas as pd
import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.models.dataset import Dataset
from app.models.dataset_profile import DatasetProfile

logger = logging.getLogger(__name__)


class DataQualityScorer:
    """
    Computes a numerical Data Quality Score (0-100) and maps it to a grade
    (Excellent, Good, Fair, Poor). The score is based on completeness, uniqueness,
    and cardinality penalties.
    """

    @staticmethod
    def calculate_score(
        df: pd.DataFrame,
        numeric_cols: List[str],
        categorical_cols: List[str],
        boolean_cols: List[str],
        datetime_cols: List[str],
    ) -> Tuple[float, str, Dict[str, Any]]:
        score = 100.0
        penalties = {}

        # 1. Missing Values Penalty (Max 30 points)
        total_elements = df.size
        total_missing = int(df.isna().sum().sum())
        total_missing_pct = (total_missing / total_elements * 100.0) if total_elements > 0 else 0.0
        # Deduct 0.5 points for every 1% missingness, capped at 30 points
        missing_penalty = min(30.0, total_missing_pct * 0.5)
        score -= missing_penalty
        penalties["missing_values"] = {
            "penalty": float(missing_penalty),
            "percentage": float(total_missing_pct),
            "count": total_missing,
        }

        # 2. Duplicate Rows Penalty (Max 15 points)
        dup_count = int(df.duplicated().sum())
        dup_pct = (dup_count / len(df) * 100.0) if len(df) > 0 else 0.0
        # Deduct 0.3 points for every 1% duplicate rate, capped at 15 points
        dup_penalty = min(15.0, dup_pct * 0.3)
        score -= dup_penalty
        penalties["duplicate_rows"] = {
            "penalty": float(dup_penalty),
            "percentage": float(dup_pct),
            "count": dup_count,
        }

        # 3. Column-level Penalties (Max 35 points total)
        num_cols = len(df.columns)
        empty_cols = 0
        constant_cols = 0
        high_card_cols = 0

        for col in df.columns:
            series = df[col]
            missing_pct = series.isna().mean() * 100.0
            if missing_pct == 100.0:
                empty_cols += 1
            else:
                non_na = series.dropna()
                nunique = non_na.nunique()
                if nunique == 1:
                    constant_cols += 1
                elif col in categorical_cols:
                    # High cardinality: more than 10 non-null values, and unique ratio > 90%
                    if len(non_na) > 10 and (nunique / len(non_na)) > 0.9:
                        high_card_cols += 1

        if num_cols > 0:
            # 15 points max for empty columns
            empty_penalty = min(15.0, (empty_cols / num_cols) * 15.0)
            # 10 points max for constant columns
            const_penalty = min(10.0, (constant_cols / num_cols) * 10.0)
            # 10 points max for high-cardinality categorical columns (excluding standard ID names)
            high_card_penalty = min(10.0, (high_card_cols / num_cols) * 10.0)
        else:
            empty_penalty = const_penalty = high_card_penalty = 0.0

        score -= (empty_penalty + const_penalty + high_card_penalty)
        penalties["columns"] = {
            "empty": {"count": empty_cols, "penalty": float(empty_penalty)},
            "constant": {"count": constant_cols, "penalty": float(const_penalty)},
            "high_cardinality": {"count": high_card_cols, "penalty": float(high_card_penalty)},
        }

        # Clip final score
        score = max(0.0, min(100.0, float(score)))

        # Assign Quality Levels
        if score >= 85:
            level = "Excellent"
        elif score >= 70:
            level = "Good"
        elif score >= 50:
            level = "Fair"
        else:
            level = "Poor"

        return score, level, penalties


class MlRecommendationEngine:
    """
    Heuristically infers the likely target column and recommends an ML task
    (Classification, Regression, Clustering, or Time Series).
    """

    @staticmethod
    def infer_task_and_target(
        df: pd.DataFrame,
        numeric_cols: List[str],
        categorical_cols: List[str],
        boolean_cols: List[str],
        datetime_cols: List[str],
    ) -> Tuple[str, str | None, float, Dict[str, Any]]:
        num_rows = len(df)
        if num_rows == 0 or len(df.columns) == 0:
            return "Clustering", None, 0.0, {"explanation": "Empty dataset"}

        target_candidates = []

        for idx, col in enumerate(df.columns):
            col_lower = col.lower()
            score_col = 0.0

            # Heuristic 1: Is it the last column?
            if idx == len(df.columns) - 1:
                score_col += 0.3

            # Heuristic 2: Target keyword naming
            target_keywords = [
                "target", "label", "class", "outcome", "status", "churn",
                "survived", "price", "revenue", "y", "clicked", "output",
                "pred", "sale", "default", "rating"
            ]
            if any(k == col_lower or f"_{k}" in col_lower or f"{k}_" in col_lower for k in target_keywords):
                score_col += 0.5
            elif col_lower == "y":
                score_col += 0.6

            # Heuristic 3: Penalize ID-like columns
            id_keywords = [
                "id", "uuid", "index", "row", "key", "user_id", "session_id",
                "customer_id", "transaction_id", "file_name", "filename"
            ]
            if col_lower in id_keywords or col_lower.endswith("_id") or col_lower.startswith("id_") or col_lower.endswith("id"):
                score_col -= 0.8

            # Heuristic 4: Exclude continuous/constant unique values
            nunique = df[col].nunique()
            if nunique <= 1 or nunique == num_rows:
                score_col -= 0.9

            # Heuristic 5: Exclude datetime columns
            if col in datetime_cols:
                score_col -= 0.5

            target_candidates.append((col, score_col))

        # Sort and select best candidate
        best_col, raw_score = max(target_candidates, key=lambda x: x[1])

        # Map raw heuristic score (roughly -1.7 to 1.4) to confidence percentage
        confidence = max(10.0, min(99.0, float((raw_score + 1.0) / 2.2 * 100.0)))
        has_reliable_target = raw_score > 0.0

        has_datetime = len(datetime_cols) > 0
        recommended_task = "Classification"

        if has_reliable_target:
            target_series = df[best_col].dropna()
            nunique_target = target_series.nunique()

            # Date check + numeric sales/demand/price keyword -> Time Series
            time_series_keywords = ["price", "demand", "sales", "revenue", "count", "amount", "temp", "temperature"]
            if has_datetime and any(x in best_col.lower() for x in time_series_keywords):
                recommended_task = "Time Series"
            elif pd.api.types.is_numeric_dtype(df[best_col]):
                # Discrete numeric classes vs continuous numeric target
                if nunique_target <= 15 or (nunique_target < 0.05 * len(df) and nunique_target < 50):
                    recommended_task = "Classification"
                else:
                    recommended_task = "Regression"
            elif pd.api.types.is_bool_dtype(df[best_col]) or best_col in boolean_cols:
                recommended_task = "Classification"
            else:
                recommended_task = "Classification"
        else:
            # Unsupervised
            if has_datetime:
                recommended_task = "Time Series"
            else:
                recommended_task = "Clustering"
            best_col = None
            confidence = 0.0

        explanation = {
            "inferred_target": best_col,
            "confidence": confidence,
            "recommended_task": recommended_task,
            "reasons": [
                f"Recommended task is '{recommended_task}' based on column characteristics.",
                f"Target column '{best_col}' identified with confidence score of {confidence:.1f}%."
                if best_col else "No obvious target column identified; clustering recommended."
            ],
        }

        return recommended_task, best_col, confidence, explanation


def _clean_for_json(val: Any) -> Any:
    """Helper to convert NumPy/Pandas types to standard JSON-compatible Python types."""
    # Guard against non-scalar types (list, dict, ndarray) before calling pd.isna,
    # which raises ValueError: "The truth value of an array is ambiguous" on iterables.
    if isinstance(val, (list, dict, np.ndarray)):
        return str(val)
    try:
        if pd.isna(val):
            return None
    except (TypeError, ValueError):
        return str(val)
    if isinstance(val, (np.integer, int)):
        return int(val)
    if isinstance(val, (np.floating, float)):
        if math.isnan(val) or math.isinf(val):
            return None
        return float(val)
    if isinstance(val, (np.bool_, bool)):
        return bool(val)
    if isinstance(val, pd.Timestamp):
        return val.isoformat()
    return str(val)


def analyze_csv(filepath: str) -> Dict[str, Any]:
    """
    Core dataset analysis engine using Pandas.
    Automatically detects the file type (CSV vs. Excel) and loads it.
    Computes summary statistics, quality checks, and ML tasks.
    """
    path = Path(filepath)
    ext = path.suffix.lower()

    # 1. Load dataset with automatic detection and fallbacks
    if ext in (".xlsx", ".xls"):
        logger.info("Auto-detected Excel file. Loading: %s", filepath)
        try:
            if ext == ".xlsx":
                try:
                    df = pd.read_excel(filepath, engine="openpyxl")
                except ImportError as ie:
                    logger.error("openpyxl engine missing for .xlsx file: %s", str(ie))
                    raise ValueError("Excel engine (openpyxl) is missing.")
            else:
                try:
                    df = pd.read_excel(filepath, engine="xlrd")
                except ImportError as ie:
                    logger.error("xlrd engine missing for .xls file: %s", str(ie))
                    raise ValueError("Excel engine (xlrd) is missing.")
        except ValueError:
            raise
        except Exception as e:
            logger.error("Failed to parse Excel file: %s. Error: %s", filepath, str(e))
            err_str = str(e).lower()
            if "openpyxl" in err_str:
                raise ValueError("Excel engine (openpyxl) is missing.")
            elif "xlrd" in err_str:
                raise ValueError("Excel engine (xlrd) is missing.")
            else:
                raise ValueError(f"Unable to read Excel workbook.")
    else:
        logger.info("Loading CSV file: %s", filepath)
        df = None
        encodings = ["utf-8", "utf-8-sig", "latin1", "cp1252"]
        last_error = None
        for encoding in encodings:
            try:
                logger.info("Attempting to parse CSV with encoding: %s", encoding)
                df = pd.read_csv(filepath, encoding=encoding, on_bad_lines="skip")
                logger.info("Successfully loaded CSV file with encoding: %s", encoding)
                break
            except (UnicodeDecodeError, LookupError) as e:
                logger.warning("Encoding %s failed for %s. Error: %s", encoding, filepath, str(e))
                last_error = e
            except Exception as e:
                logger.error("Parser error reading CSV with encoding %s: %s", encoding, str(e))
                last_error = e

        if df is None:
            logger.error("Failed to load CSV file with all standard encodings: %s", filepath)
            if last_error and "decode" in str(last_error).lower():
                raise ValueError("Unsupported file encoding.")
            else:
                raise ValueError("Pandas failed to parse the uploaded dataset.")

    row_count = len(df)
    col_count = len(df.columns)
    memory_usage = int(df.memory_usage(deep=True).sum())


    # 2. Column Categorization
    numeric_cols = []
    categorical_cols = []
    boolean_cols = []
    datetime_cols = []

    for col in df.columns:
        # Check datetime
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            datetime_cols.append(col)
        # Check boolean
        elif pd.api.types.is_bool_dtype(df[col]):
            boolean_cols.append(col)
        # Check numeric
        elif pd.api.types.is_numeric_dtype(df[col]):
            # Numeric columns with values only in (0, 1, NaN) can be considered boolean
            unique_vals = df[col].dropna().unique()
            if len(unique_vals) <= 2 and set(unique_vals).issubset({0, 1, 0.0, 1.0}):
                boolean_cols.append(col)
            else:
                numeric_cols.append(col)
        # Check object / string
        else:
            # Fallback datetime inferring
            is_dt = False
            col_lower = col.lower()
            if any(k in col_lower for k in ["date", "time", "timestamp", "_at"]):
                try:
                    parsed = pd.to_datetime(df[col], errors='coerce')
                    if parsed.notna().sum() > 0.5 * len(df):
                        datetime_cols.append(col)
                        is_dt = True
                except Exception:
                    pass

            if not is_dt:
                # Fallback boolean inferring
                unique_vals = df[col].dropna().unique()
                unique_vals_str = {str(x).strip().lower() for x in unique_vals}
                if len(unique_vals_str) <= 2 and unique_vals_str.issubset({"true", "false", "yes", "no", "t", "f", "1", "0"}):
                    boolean_cols.append(col)
                else:
                    categorical_cols.append(col)

    # 3. Missing values analysis
    missing_counts = df.isna().sum().to_dict()
    missing_pcts = (df.isna().mean() * 100.0).to_dict()
    total_elements = df.size
    total_missing = int(df.isna().sum().sum())
    total_missing_pct = (total_missing / total_elements * 100.0) if total_elements > 0 else 0.0

    missing_info = {
        "columns": {col: {"count": int(missing_counts[col]), "percentage": float(missing_pcts[col])} for col in df.columns},
        "total_missing_count": total_missing,
        "total_missing_percentage": float(total_missing_pct),
    }

    # 4. Duplicate rows analysis
    dup_count = int(df.duplicated().sum())
    dup_pct = (dup_count / row_count * 100.0) if row_count > 0 else 0.0
    duplicates_info = {
        "count": dup_count,
        "percentage": float(dup_pct),
    }

    # 5. Column-specific statistics
    col_profiles = {}

    # Numeric statistics
    for col in df.columns:
        col_type = "categorical"
        if col in numeric_cols:
            col_type = "numeric"
        elif col in boolean_cols:
            col_type = "boolean"
        elif col in datetime_cols:
            col_type = "datetime"

        series = df[col]
        non_na = series.dropna()

        profile = {
            "name": col,
            "type": col_type,
            "missing_count": int(missing_counts[col]),
            "missing_percentage": float(missing_pcts[col]),
            "cardinality": int(series.nunique()),
        }

        # Calculate statistics based on type
        if col_type == "numeric" and not non_na.empty:
            mode_series = non_na.mode()
            mode_val = _clean_for_json(mode_series.iloc[0]) if not mode_series.empty else None

            profile["statistics"] = {
                "mean": _clean_for_json(non_na.mean()),
                "median": _clean_for_json(non_na.median()),
                "mode": mode_val,
                "std": _clean_for_json(non_na.std()),
                "var": _clean_for_json(non_na.var()),
                "min": _clean_for_json(non_na.min()),
                "max": _clean_for_json(non_na.max()),
                "q1": _clean_for_json(non_na.quantile(0.25)),
                "q3": _clean_for_json(non_na.quantile(0.75)),
            }
        elif col_type in ("categorical", "boolean") and not non_na.empty:
            mode_series = non_na.mode()
            mode_val = _clean_for_json(mode_series.iloc[0]) if not mode_series.empty else None
            # Limit sample values to avoid bloating DB
            unique_sample = [_clean_for_json(x) for x in non_na.unique()[:20]]

            profile["statistics"] = {
                "unique_values": unique_sample,
                "most_frequent": mode_val,
            }
        else:
            profile["statistics"] = {}

        col_profiles[col] = profile

    # 6. Data Quality Assessment
    quality_score, quality_level, quality_penalties = DataQualityScorer.calculate_score(
        df=df,
        numeric_cols=numeric_cols,
        categorical_cols=categorical_cols,
        boolean_cols=boolean_cols,
        datetime_cols=datetime_cols,
    )
    quality_info = {
        "score": quality_score,
        "level": quality_level,
        "penalties": quality_penalties,
    }

    # 7. ML Recommendations
    rec_task, rec_target, confidence, rec_explanation = MlRecommendationEngine.infer_task_and_target(
        df=df,
        numeric_cols=numeric_cols,
        categorical_cols=categorical_cols,
        boolean_cols=boolean_cols,
        datetime_cols=datetime_cols,
    )
    ml_recommendation = {
        "recommended_task": rec_task,
        "recommended_target": rec_target,
        "confidence": confidence,
        "explanation": rec_explanation,
    }

    # 8. Enhancement: Dataset Preview (First 10 rows)
    preview_df = df.head(10)
    preview_data = []
    for _, row in preview_df.iterrows():
        preview_data.append({k: _clean_for_json(v) for k, v in row.items()})

    # Assemble complete profile dictionary
    profile_data = {
        "general": {
            "row_count": row_count,
            "column_count": col_count,
            "memory_usage": memory_usage,
            "column_types": {
                "numeric": numeric_cols,
                "categorical": categorical_cols,
                "boolean": boolean_cols,
                "datetime": datetime_cols,
            },
        },
        "missing_values": missing_info,
        "duplicates": duplicates_info,
        "columns": col_profiles,
        "quality": quality_info,
        "ml_recommendation": ml_recommendation,
        "preview": preview_data,
    }

    return profile_data


async def profile_dataset(dataset_id: int, file_path: str, db: AsyncSession) -> None:
    """
    Asynchronous task runner to perform dataset profiling.
    Updates the dataset status to profiling -> completed/failed and creates/updates
    the corresponding DatasetProfile record.
    """
    logger.info("Starting profile generation for dataset_id=%s file_path=%s", dataset_id, file_path)
    
    # 1. Update status to 'profiling'
    await db.execute(
        update(Dataset)
        .where(Dataset.id == dataset_id)
        .values(status="profiling")
    )
    await db.commit()

    try:
        # Check that file exists on disk
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found on disk: {file_path}")

        # Run profiling analysis (CPU bound, but run inside threadpool/process by caller or direct execution)
        # Note: If called in FastAPI background tasks, it runs in a threadpool automatically.
        profile_results = analyze_csv(str(path))

        # Extract frequently queried columns
        quality_score = profile_results["quality"]["score"]
        quality_level = profile_results["quality"]["level"]
        rec_task = profile_results["ml_recommendation"]["recommended_task"]
        rec_target = profile_results["ml_recommendation"]["recommended_target"]
        row_count = profile_results["general"]["row_count"]
        col_count = profile_results["general"]["column_count"]

        # Check if profile already exists (e.g. re-profile case)
        stmt = select(DatasetProfile).where(DatasetProfile.dataset_id == dataset_id)
        result = await db.execute(stmt)
        existing_profile = result.scalar_one_or_none()

        if existing_profile:
            # Update existing
            existing_profile.quality_score = quality_score
            existing_profile.quality_level = quality_level
            existing_profile.recommended_task = rec_task
            existing_profile.recommended_target = rec_target
            existing_profile.row_count = row_count
            existing_profile.column_count = col_count
            existing_profile.profile_data = profile_results
            existing_profile.updated_at = datetime.now(timezone.utc)
        else:
            # Create new
            new_profile = DatasetProfile(
                dataset_id=dataset_id,
                quality_score=quality_score,
                quality_level=quality_level,
                recommended_task=rec_task,
                recommended_target=rec_target,
                row_count=row_count,
                column_count=col_count,
                profile_data=profile_results,
            )
            db.add(new_profile)

        # Update dataset status to 'completed'
        await db.execute(
            update(Dataset)
            .where(Dataset.id == dataset_id)
            .values(status="completed")
        )
        await db.commit()
        logger.info("Successfully completed profile generation for dataset_id=%s", dataset_id)

    except Exception as e:
        logger.exception("Failed to generate profile for dataset_id=%s", dataset_id)
        
        # Determine user-friendly error message
        error_msg = "An unexpected error occurred during profiling."
        err_str = str(e)
        
        if isinstance(e, FileNotFoundError) or "file not found" in err_str.lower():
            error_msg = "Dataset file not found."
        elif "openpyxl" in err_str.lower():
            error_msg = "Excel engine (openpyxl) is missing."
        elif "xlrd" in err_str.lower():
            error_msg = "Excel engine (xlrd) is missing."
        elif "unicodedecodeerror" in type(e).__name__.lower() or "codec" in err_str.lower():
            error_msg = "Unsupported file encoding."
        elif "parsererror" in type(e).__name__.lower() or "parser" in err_str.lower() or "empty_col" in err_str.lower():
            error_msg = "Pandas failed to parse the uploaded dataset."
        elif "zipfile.badzipfile" in type(e).__name__.lower() or "invalidfileexception" in type(e).__name__.lower() or "xlsx" in err_str.lower() or "excel" in err_str.lower():
            error_msg = "Unable to read Excel workbook."

        # If analyze_csv raised a custom ValueError containing one of the friendly strings, we use it directly
        for friendly_candidate in [
            "Excel engine (openpyxl) is missing.",
            "Excel engine (xlrd) is missing.",
            "Unsupported file encoding.",
            "Pandas failed to parse the uploaded dataset.",
            "Unable to read Excel workbook.",
            "Dataset file not found."
        ]:
            if friendly_candidate in err_str:
                error_msg = friendly_candidate
                break

        # Update dataset status to 'failed' and write error message
        await db.execute(
            update(Dataset)
            .where(Dataset.id == dataset_id)
            .values(status="failed", error_message=error_msg)
        )
        await db.commit()
