import streamlit as st
import os
from typing import TypedDict, List
from langchain_openai import ChatOpenAI
from langchain_core.pydantic_v1 import BaseModel
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, END
from tavily import TavilyClient
import re
import uuid
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize model and Tavily client
model = ChatOpenAI(model="gpt-4o-mini", temperature=0)
tavily = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])

# Define state
class AgentState(TypedDict):
    task: str
    content: List[str]
    code: str
    critique: str
    revision_number: int
    max_revisions: int

# Define prompts
RESEARCH_PROMPT = """You are an AWS Terraform research expert.  
Given a user’s request, follow these steps:

1. **Parse the Request**  
   - Identify all AWS services/resources mentioned (e.g., VPC, EC2, IAM, S3, RDS).  

2. **Define Query Goals**  
   - For each service, decide whether you need:
     - Official Terraform provider docs  
     - Official AWS docs  
     - Community blog posts or GitHub samples  

3. **Generate Search Queries**  
   - Craft exactly three concise search queries, each including “Terraform” plus one or more of the identified AWS services.
   - Prioritize queries that will return high‑quality, up‑to‑date Terraform guides.

---

User’s request:  
{task}

**Output only three search queries, one per line**, for example:  
"""

CODE_GEN_PROMPT = """You are an AWS Terraform expert.  
Given a user’s request and any supporting research, follow these steps:

1. **Parse the Request**  
   - List required AWS resources (VPC, subnets, IGW, route tables, security groups, EC2 instance, etc.).  
   - Note special requirements (public vs. private, CIDR ranges, SSH/HTTP, key‑pair name, tags, etc.).

2. **Define Variables**  
   - Decide which values to parameterize (region, CIDR blocks, instance_type, key_name, etc.).  
   - Sketch a `variables.tf` section with names, types, descriptions, and sensible defaults.

3. **Select Data Sources**  
   - Include lookups for latest AMIs or other AWS‑provided values.

4. **Compose Resource Blocks**  
   - Order logically:
     1. VPC  
     2. Internet Gateway  
     3. Route Table & Association  
     4. Subnets  
     5. Security Groups  
     6. EC2 Instances  
   - Use clear resource names, tags, and explicit dependencies.

5. **Define Outputs**  
   - Expose useful values (public IP, instance_id, VPC ID, etc.).

6. **Generate Final HCL**  
   - Produce a single `main.tf` code block that includes:
     - `provider`  
     - `variables`  
     - `data` (for AMI)  
     - All `resource` blocks  
     - `output` blocks  
   - Ensure it’s production‑ready (best practices, clean naming).

---

User request:  
{task}

Research content:  
{content}

**Output only the Terraform code** inside one HCL code fence:

```hcl
# your generated Terraform configuration here
```"""

CODE_REVIEW_PROMPT ="""You are an AWS Terraform review expert.  
Given a user’s request and a generated Terraform configuration, follow these steps:

1. **Parse the Request**  
   - List the required AWS resources and constraints from the user’s request.

2. **Analyze the Code**  
   - Identify which resources, data sources, variables, and outputs are present.
   - Match them against the parsed requirements.

3. **Validate Correctness**  
   - Check that each required resource is implemented.
   - Confirm that dependencies, attribute values (CIDR blocks, ports, instance types, etc.), and providers align with best practices.

4. **Assess Best Practices**  
   - Ensure use of data sources for AMIs, parameterization via variables, clear naming, tagging, and explicit dependencies.
   - Verify networking setup (subnets, IGW, routes) is complete.
   - Check for security group egress rules and least‑privilege principles.

5. **Produce the Review**  
   - If everything is correct, respond:  
     `"The code is valid."`  
   - Otherwise, list specific issues and recommended fixes.

---

User’s request:  
{task}

Terraform code:  
{code}

**Output only your review.**  
"""
# Define structured output for queries
class Queries(BaseModel):
    queries: List[str]

# Define nodes
def research_node(state: AgentState):
    messages = [
        SystemMessage(content=RESEARCH_PROMPT.format(task=state['task'])),
        HumanMessage(content="Generate search queries.")
    ]
    queries = model.with_structured_output(Queries).invoke(messages)
    content = state['content'] or []
    for q in queries.queries:
        response = tavily.search(query=q, max_results=2)
        for r in response['results']:
            content.append(r['content'])
    return {"content": content}

def code_gen_node(state: AgentState):
    content = "\n\n".join(state['content'] or [])
    critique = state.get('critique', '')
    prompt = CODE_GEN_PROMPT.format(task=state['task'], content=content)
    if critique:
        prompt += f"\n\nPrevious critique: {critique}\nPlease address the issues mentioned."
    messages = [
        SystemMessage(content=prompt),
        HumanMessage(content="Generate the Terraform configuration.")
    ]
    response = model.invoke(messages)
    code = response.content
    # Extract code from the response
    match = re.search(r'```hcl\n(.*?)```', code, re.DOTALL)
    if match:
        code = match.group(1).strip()
    else:
        code = code.strip()
    return {
        "code": code,
        "revision_number": state.get("revision_number", 0) + 1
    }

def code_reviewer_node(state: AgentState):
    prompt = CODE_REVIEW_PROMPT.format(task=state['task'], code=state['code'])
    messages = [
        SystemMessage(content=prompt),
        HumanMessage(content="Review the Terraform code.")
    ]
    response = model.invoke(messages)
    critique = response.content
    return {"critique": critique}

# Define routing function
def route_after_review(state):
    if state["revision_number"] > state["max_revisions"] or "The code is valid" in state["critique"]:
        return END
    else:
        return "code_gen"

# Set up the graph
builder = StateGraph(AgentState)
builder.add_node("research", research_node)
builder.add_node("code_gen", code_gen_node)
builder.add_node("code_reviewer", code_reviewer_node)
builder.set_entry_point("research")
builder.add_edge("research", "code_gen")
builder.add_edge("code_gen", "code_reviewer")
builder.add_conditional_edges(
    "code_reviewer",
    route_after_review,
    {"code_gen": "code_gen", END: END}
)
graph = builder.compile()

# Streamlit app
st.title("Terraform Configuration Generator")

# User input
task = st.text_area("Describe your AWS infrastructure needs (e.g., 'Create an EC2 instance and an RDS database'):", height=100)

if st.button("Generate Terraform Configuration"):
    if task:
        with st.spinner("Generating configuration..."):
            # Generate a unique thread ID for this run
            thread_id = str(uuid.uuid4())
            initial_state = {
                "task": task,
                "content": [],
                "code": "",
                "critique": "",
                "revision_number": 0,
                "max_revisions": 3,
                "configurable": {"thread_id": thread_id}
            }
            # Collect all states during execution
            states = []
            for s in graph.stream(initial_state):
                states.append(s)
            # Extract the second-to-last and final states
            if len(states) >= 2:
                second_last_state = states[-2]
                final_state = states[-1]
                
                print(second_last_state["code_gen"]["code"])
                if "code_gen" in second_last_state and second_last_state["code_gen"]:
                    st.code(second_last_state["code_gen"]["code"], language="hcl")
                    st.download_button(
                        label="Download Second-to-Last Configuration",
                        data=second_last_state["code_gen"]["code"],
                        file_name="second_last_main.tf",
                        mime="text/plain"
                    )
                else:
                    st.warning("No code found in the second-to-last state.")
    else:
        st.warning("Please provide a description of your infrastructure needs.")