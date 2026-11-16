
# Vehicle Damage Vision
### AI-Powered Vehicle Damage Assessment and Insurance Claim Generation

Vehicle Damage Vision is an AI-powered application that automates key stages of vehicle damage assessment and insurance claim preparation.

The system accepts vehicle damage images and claim information, identifies visible damage, estimates repair costs, retrieves relevant insurance policy information, and generates a structured claim report.

The project is developed by a four-member team, with each member responsible for a dedicated module.

## Project Workflow

```text
Vehicle Image + Claim Details
              |
              v
     Role 1: Vision Analysis
              |
              v
     Role 2: Repair Cost Estimation
              |
              v
     Role 3: Policy Retrieval and Claim Writing
              |
              v
     Role 4: System Integration
              |
              v
      Final Claim Assessment
              |
              v
        PDF Report
```

## Main Modules

### Role 1 – Vehicle Damage Detection
- Analyses uploaded vehicle images.
- Identifies visible damaged vehicle parts.
- Classifies damage type and severity.
- Uses Gemini-based vision analysis.
- Produces structured output through Contract A.

### Role 2 – Repair Cost Estimation
- Processes the detected damage information.
- Estimates repair and replacement costs.
- Calculates depreciation and estimated claimable amounts.
- Produces structured cost assessment through Contract B.

### Role 3 – Insurance Policy Analysis
- Retrieves relevant information from insurance policy documents.
- Uses Retrieval-Augmented Generation (RAG).
- Uses ChromaDB for policy document retrieval.
- Generates policy-based claim explanations.
- Produces claim narrative through Contract C.

### Role 4 – Integration and Dashboard
- Connects all four modules.
- Provides a Streamlit-based user interface.
- Accepts vehicle details, claim information and uploaded images.
- Displays damage assessment, cost estimation and policy analysis.
- Generates downloadable claim reports.

## Technology Stack

| Component | Technology |
|---|---|
| Programming Language | Python |
| User Interface | Streamlit |
| AI Vision | Google Gemini |
| Retrieval-Augmented Generation | RAG |
| Vector Database | ChromaDB |
| Policy Processing | PDF-based document retrieval |
| Testing | Pytest |
| Version Control | Git and GitHub |
| Report Generation | PDF |

## Project Structure

```text
vehicle-damage-vision/
│
├── src/
│   ├── vision/             # Role 1 - Damage detection
│   ├── cost/               # Role 2 - Cost estimation
│   ├── rag/                # Role 3 - Policy analysis
│   └── integration/        # Role 4 - Integrated application
│
├── schemas/                # Shared data contracts
├── mocks/                  # Sample contract data
├── tests/                  # Automated tests
├── prompts/                # AI prompt templates
├── eval/                   # Vision model evaluation
├── data/                   # Project data
├── docs/                   # Project documentation
│
├── requirements.txt
├── requirements-dev.txt
├── .env.example
└── README.md
```

## Installation and Setup

### 1. Clone the repository

```bash
git clone https://github.com/Aarti-panchal01/vehicle-damage-vision.git
cd vehicle-damage-vision
```

### 2. Create a virtual environment

```powershell
python -m venv .venv
```

### 3. Activate the environment

```powershell
.venv\Scripts\Activate.ps1
```

### 4. Install dependencies

```powershell
python -m pip install -r requirements.txt -r requirements-dev.txt
```

### 5. Configure API keys

Create a `.env` file in the project root and configure the required API credentials.

Refer to `.env.example` for the expected variable names.

Never upload API keys or credentials to GitHub.

## Running the Application

Run the following command from the project root:

```powershell
python -m streamlit run src/integration/app.py --server.fileWatcherType none
```

The Streamlit application will open in your browser.

## Running Tests

Execute the automated test suite:

```powershell
python -m pytest -q
```

The project has successfully completed **291 automated tests** in the tested environment.

## Sample Output

The integrated application produces:

- Vehicle damage identification.
- Damage severity and confidence information.
- Estimated repair cost and depreciation.
- Relevant insurance policy evidence.
- AI-generated claim summary.
- Downloadable claim report.

## Important Limitations

- The system identifies visible damage and cannot reliably determine hidden structural damage from images alone.
- Repair cost estimates are preliminary estimates, not confirmed workshop quotations.
- Policy interpretations depend on the uploaded policy documents and retrieved evidence.
- Depreciation assumptions must be checked against the applicable insurer policy before relying on the claimable estimate.
- Final claim approval and settlement remain the responsibility of the insurance company.

## Team

This project is developed collaboratively by a four-member team.

Each member contributes to a dedicated module, and Role 4 integrates the individual components into a unified application.

## Repository

GitHub: https://github.com/Aarti-panchal01/vehicle-damage-vision
