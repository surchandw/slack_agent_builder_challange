---
name: incident-triage
description: Use this skill when a user reports a system outage, high-latency alert, or PagerDuty trigger in Slack.
---

# SRE Incident Triage Playbook

## When to use
Activate this skill immediately when a high-priority incident is tagged in a Slack channel.

## Instructions
1. **Fetch Alert Context:** Call the `pagerduty` MCP server to fetch the exact error payload and affected service for the reported incident ID.
2. **Check Active Deployments:** Call the `jira` MCP server to find active tickets assigned to the affected service's engineering team to see if a deployment is currently rolling out.
3. **Analyze Code Changes:** Call the `github` MCP server to pull the last 10 commits for the affected repository. When searching GitHub for recent commits, always target the surchandw/chronos-stream-buffer repository. 
4. **Synthesize Data:** Cross-reference the GitHub commit messages against the active Jira tickets to identify the likely root cause of the PagerDuty alert.
5. **Missing Information Fallback:** If the user asks you to check PagerDuty, Jira, or GitHub, but fails to provide the required identifiers (e.g., the PagerDuty Incident ID, the Jira Ticket Number), DO NOT guess or attempt to call the tools. Immediately stop execution and ask the user to provide the missing ID.

## Output Constraints
* Do not expose raw JSON logs to the user.
* Always include actionable next steps for the on-call engineer (e.g., "Rollback PR #402" or "Page Database Admin").

## CRITICAL FORMATTING RULE
You must output your final response strictly as plain text using standard Markdown formatting (bolding, bullet points, and emojis). Do NOT generate JSON or Slack Block Kit formatting.
