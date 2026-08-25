# RecallMate CSV Validator

RecallMate CSV Validator is a Streamlit-based application designed to clean and validate patient recall lists. It ensures that CSV files containing contact information (NHS number, Date of Birth, Phone, First Name, and Email) are standardized and error-free before being used for messaging campaigns (e.g., vaccinations, blood tests, or reviews).

## 🚀 Features

- **Smart Column Mapping**: Automatically guesses which columns in your uploaded CSV correspond to required fields (NHS Number, DOB, Phone, etc.).
- **Data Validation & Cleaning**:
    - **NHS Number**: Extracts and validates 10-digit numbers.
    - **Date of Birth**: Parses various date formats and normalizes them to `DD/MM/YYYY`.
    - **Mobile Numbers**: Extracts UK-formatted mobile numbers and standardizes them to a single format.
    - **Email**: Cleans and validates email addresses, even if they contain extra notes in the cell.
    - **First Name**: Normalizes text to clean single-space formatting.
- **Error Reporting**: Provides a clear summary of valid rows, rejected rows (with specific reasons), and empty rows removed.
- **Batch Export**: 
    - Split large lists into smaller, manageable CSV files.
    - Choose between "Batch size" (rows per file) or "Number of batches" (equal distribution).
    - Download all batches as a single `.zip` file.
- **Instant Preview**: View clean data, rejected rows, and the original upload side-by-side.

## 🛠️ Installation & Setup

### Prerequisites

- Python 3.10 or higher
- `pip` (Python package installer)

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/your-username/recallmate-csv-validator.git
   cd recallmate-csv-validator
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

### Running the App

To launch the Streamlit application, run:

```bash
streamlit run app.py
```

The app will be available at `http://localhost:8501`.

## 📂 Project Structure

- `app.py`: The main Streamlit application logic and UI.
- `validator.py`: The core engine containing data validation, normalization, and batching logic.
- `requirements.txt`: List of Python dependencies.
- `example_csv/`: Sample CSV files for testing.

## 🧪 How It Works

### Validation Logic

The validator uses a strict set of rules to ensure data quality:
- **Required Fields**: A row is rejected if it lacks an NHS number, Date of Birth, First Name, or a valid Mobile Number.
- **Sanitization**: Extra whitespace, inconsistent date formats, and non-numeric characters in phone numbers are automatically cleaned.
- **Reasoning**: Every rejected row includes a "Reason" column explaining exactly why it failed validation (e.g., "Missing first name" or "Invalid NHS number").

### Batching Logic

When exporting, the tool can split a single large file into multiple smaller files to comply with messaging platform limits:
- **By Size**: If you specify 100 rows, each file will contain up to 100 rows.
- **By Count**: If you specify 5 batches, the rows will be distributed as evenly as possible across 5 files.

## 📝 Requirements

- `streamlit`
- `pandas`
- `python-dateutil`

## ⚖️ License

[Specify your license here, e.g., MIT]
