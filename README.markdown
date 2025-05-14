# Terraform Configuration Generator

## Overview

This Streamlit application generates production-ready Terraform configurations for AWS infrastructure based on user input. It leverages LangChain, OpenAI's GPT-4o-mini model, Tavily for research, and LangGraph to orchestrate a multi-step workflow that includes research, code generation, and code review. The app ensures the generated Terraform code adheres to best practices and meets user requirements through iterative refinement.

## Features

- **User Input**: Accepts natural language descriptions of AWS infrastructure needs (e.g., "Create an EC2 instance and an RDS database").
- **Research**: Automatically generates search queries and retrieves relevant Terraform and AWS documentation using Tavily.
- **Code Generation**: Produces clean, parameterized Terraform HCL code (`main.tf`) with variables, data sources, resources, and outputs.
- **Code Review**: Validates the generated code for correctness, best practices, and alignment with user requirements, iterating up to three times if needed.
- **Output**: Displays the generated Terraform configuration and provides a download option for the code.

## Prerequisites

- Python 3.8+
- Streamlit
- LangChain
- OpenAI API key (for GPT-4o-mini)
- Tavily API key (for research)
- AWS credentials configured for Terraform (not directly used in the app but required for applying the generated code)

## Installation

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/shubham-309/TF-script-generator.git
   cd TF-script-generator
   ```

2. **Set Up a Virtual Environment** (optional but recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

   Example `requirements.txt`:
   ```
   streamlit
   langchain
   langchain-openai
   langgraph
   tavily-python
   python-dotenv
   ```

4. **Configure Environment Variables**:
   Create a `.env` file in the project root with the following:
   ```
   TAVILY_API_KEY=your-tavily-api-key
   OPENAI_API_KEY=your-openai-api-key
   ```

## Usage

1. **Run the Streamlit App**:
   ```bash
   streamlit run app.py
   ```

2. **Access the App**:
   Open your browser and navigate to `http://localhost:8501`.

3. **Provide Input**:
   - Enter a description of your AWS infrastructure needs in the text area (e.g., "Create a VPC with two public subnets and an EC2 instance").
   - Click the "Generate Terraform Configuration" button.

4. **View and Download Output**:
   - The generated Terraform code will be displayed in a code block.
   - Use the "Download Second-to-Last Configuration" button to save the `main.tf` file.

## Application Workflow

The app uses a LangGraph workflow with three main nodes:

1. **Research Node**:
   - Parses the user’s request to identify AWS services.
   - Generates three search queries and retrieves relevant content using Tavily.
   - Stores research content in the state.

2. **Code Generation Node**:
   - Uses the user request and research content to generate Terraform HCL code.
   - Incorporates feedback from previous critiques (if any).
   - Produces a complete `main.tf` with provider, variables, data sources, resources, and outputs.

3. **Code Review Node**:
   - Validates the generated code against the user’s requirements and Terraform best practices.
   - Returns a critique with issues and fixes or confirms the code is valid.
   - Iterates back to code generation if issues are found (up to three revisions).

The workflow terminates when the code is valid or the maximum revisions (3) are reached.

## File Structure

```
TF-script-generator/
├── app.py              # Main Streamlit application
├── requirements.txt    # Python dependencies
├── .env                # Environment variables (not tracked)
└── README.md           # This file
```

## Example Input and Output

**Input**:
```
Create an EC2 instance and an RDS database
```

**Output** (example):
```hcl
provider "aws" {
  region = var.region
}

variable "region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

# ... (additional variables, data sources, resources, and outputs)
```

The code will include all necessary resources (e.g., VPC, subnets, security groups, EC2, RDS) with proper dependencies and best practices.

## Limitations

- The app relies on the quality of research content retrieved by Tavily.
- Complex or ambiguous user requests may require multiple revisions to produce correct code.
- The maximum revision limit is set to 3 to avoid infinite loops.
- AWS credentials must be configured separately to apply the generated Terraform code.
