
# Solace Agent Mesh — Developer Guide

*A unified developer reference synthesized from all uploaded Solace Agent Mesh “Developing” documentation.*

## Table of Contents
1. [Overview](#overview)
2. [Project Structure](#project-structure)
3. [Creating Agents](#creating-agents)
4. [Creating Gateways](#creating-gateways)
5. [Creating Python Tools](#creating-python-tools)
6. [Creating Service Providers](#creating-service-providers)
7. [Evaluations](#evaluations)
8. [Local Development Workflow](#local-development-workflow)

---

# Overview
Solace Agent Mesh is a distributed AI framework built on an event-driven architecture. Agents communicate using the **A2A (Agent-to-Agent) protocol**, powered by **Solace AI Connector** and the Solace Event Broker.

Developers can:
- Define autonomous agents  
- Extend agents with Python tools  
- Integrate external systems via gateways  
- Build reusable plugins  
- Evaluate agents using structured test suites  

---

# Project Structure
Agent Mesh consists of:
- Solace Event Broker  
- AI Connector  
- Distributed agents  
- Gateways  
- Service Providers  

A typical project includes YAML configs defining all components.

---

# Creating Agents
Agents encapsulate LLM-driven behavior. YAML defines:
- model  
- tools  
- subscriptions  
- publications  

Agents may use memory and call tools.

---

# Creating Gateways
Gateways adapt external systems (Slack, HTTP, Webhooks) into A2A events. They:
- Parse external events  
- Build A2A messages  
- Map user identity  
- Deliver responses back to platform  

---

# Creating Python Tools
Tools extend agent capabilities. They are typed Python functions registered in YAML.

Example:
```python
@tool(name="search_tickets")
def search_tickets(query: str):
    return ticket_api.search(query)
```

Tools must return JSON-serializable output.

---

# Creating Service Providers
Providers integrate backend systems (CRM, HR, ticketing). They:
- Authenticate  
- Subscribe  
- Process events  
- Publish results  

---

# Evaluations
Evaluations allow structured testing:
```yaml
tests:
  - name: greeting
    input: "Hello"
    expected:
      contains: ["Hi"]
```

Run via:
```
agent-mesh evaluate file.yaml
```

---

# Local Development Workflow
1. Define YAML  
2. Implement tools  
3. Run broker  
4. Launch runtime  
5. Write evaluations  
6. Deploy  
