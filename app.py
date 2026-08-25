import streamlit as st

from validator import (
    CANONICAL_COLUMNS,
    REQUIRED_COLUMNS,
    batch_summary,
    batches_to_zip_bytes,
    dataframe_to_csv_bytes,
    default_column_mapping,
    read_csv,
    sanitize_filename_prefix,
    split_dataframe_by_batch_count,
    split_dataframe_by_batch_size,
    standardize_columns,
    validate_recall_csv,
)


st.set_page_config(page_title="RecallMate CSV validator", page_icon="RM", layout="wide")
st.title(":material/verified: RecallMate CSV validator")
st.caption("Clean recall lists before sending patients vaccination, blood test, or review messages.")

uploaded_file = st.file_uploader("Upload a recall CSV", type=["csv"])


if uploaded_file is None:
    st.info("Upload a CSV to validate it. The output will use the same five column names throughout the app.")
    st.stop()

try:
    raw_df = read_csv(uploaded_file)
except Exception as exc:
    st.error(f"Could not read that CSV: {exc}")
    st.stop()

if raw_df.empty and len(raw_df.columns) == 0:
    st.error("The uploaded file does not look like a CSV with headings.")
    st.stop()

with st.expander("Column matching", expanded=True, icon=":material/table_chart:"):
    st.write("Confirm which uploaded column should be used for each RecallMate field.")

    guessed_mapping = default_column_mapping(raw_df.columns)
    available_options = ["-- not present --", *list(raw_df.columns)]
    mapping: dict[str, str | None] = {}

    mapping_columns = st.columns(5)
    for index, target_column in enumerate(CANONICAL_COLUMNS):
        guessed = guessed_mapping.get(target_column)
        default_index = available_options.index(guessed) if guessed in available_options else 0
        selected = mapping_columns[index].selectbox(
            target_column,
            available_options,
            index=default_index,
            key=f"mapping-{target_column}",
        )
        mapping[target_column] = None if selected == "-- not present --" else selected

missing_required = [column for column in REQUIRED_COLUMNS if not mapping.get(column)]
if missing_required:
    st.error("Missing required column mapping: " + ", ".join(missing_required))
    st.stop()

standardized_df = standardize_columns(raw_df, mapping)
result = validate_recall_csv(standardized_df)

st.subheader("Validation result")
metric_columns = st.columns(5)
metric_columns[0].metric("Valid rows", result.summary["valid_rows"])
metric_columns[1].metric("Rejected rows", result.summary["rejected_rows"])
metric_columns[2].metric("Empty rows removed", result.summary["empty_rows_removed"])
metric_columns[3].metric("Bad emails cleared", result.summary["invalid_emails_cleared"])
metric_columns[4].metric("Rows checked", result.summary["input_rows_after_empty_removed"])

download_columns = st.columns([1, 1, 3])
download_columns[0].download_button(
    "Download clean CSV",
    data=dataframe_to_csv_bytes(result.cleaned),
    file_name="recallmate_clean.csv",
    mime="text/csv",
    disabled=result.cleaned.empty,
)
download_columns[1].download_button(
    "Download rejected rows",
    data=dataframe_to_csv_bytes(result.rejected),
    file_name="recallmate_rejected.csv",
    mime="text/csv",
    disabled=result.rejected.empty,
)

if not result.cleaned.empty:
    with st.expander("Batch export", expanded=False, icon=":material/select_window_2:"):
        st.write(":shimmer[Split the clean recall list into multiple CSV files.]")

        batch_mode = st.radio(
            "Choose batching method",
            ["Batch size", "Number of batches"],
            horizontal=True,
        )
        filename_prefix = st.text_input("Filename prefix", value="recallmate_batch")
        zip_filename = filename_prefix.strip() or "recallmate_batch"
        safe_filename_prefix = sanitize_filename_prefix(filename_prefix)
        if safe_filename_prefix != filename_prefix.strip():
            st.caption(f"Files will use the safe prefix: {safe_filename_prefix}")

        if batch_mode == "Batch size":
            batch_size = st.slider(
                "Rows per CSV",
                min_value=1,
                max_value=len(result.cleaned),
                value=min(100, len(result.cleaned)),
                step=1,
            )
            batches = split_dataframe_by_batch_size(result.cleaned, int(batch_size))
        else:
            max_batch_count = min(30, len(result.cleaned))
            batch_count = st.slider(
                "Number of CSV files",
                min_value=1,
                max_value=max_batch_count,
                value=min(10, max_batch_count),
                step=1,
            )
            batches = split_dataframe_by_batch_count(result.cleaned, int(batch_count))

        batch_overview = batch_summary(batches, safe_filename_prefix)
        batch_columns = st.columns([1, 1, 3])
        batch_columns[0].metric("CSV files", len(batches))
        batch_columns[1].metric("Total batched rows", sum(len(batch) for batch in batches))
        batch_columns[2].download_button(
            "Download batched CSVs",
            data=batches_to_zip_bytes(batches, safe_filename_prefix),
            file_name=f"{zip_filename}.zip",
            mime="application/zip",
            disabled=not batches,
            type="primary",
        )

        st.dataframe(batch_overview, use_container_width=True, hide_index=True)

tabs = st.tabs(["Clean rows", "Rejected rows", "Uploaded preview"])

with tabs[0]:
    if result.cleaned.empty:
        st.warning("No valid recall rows were found.")
    else:
        st.dataframe(result.cleaned, use_container_width=True, hide_index=True)

with tabs[1]:
    if result.rejected.empty:
        st.success("No rows were rejected.")
    else:
        st.dataframe(result.rejected, use_container_width=True, hide_index=True)

with tabs[2]:
    preview_df = raw_df.head(100).copy()
    st.dataframe(preview_df, use_container_width=True, hide_index=True)
