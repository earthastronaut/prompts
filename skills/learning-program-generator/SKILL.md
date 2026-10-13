---
name: "learning-program-generator"
description: "A skill that provides instructions for generating personalized learning programs/curricula for self-directed learning"
---

# Learning Program Generator

## Description

Generate personalized learning programs and curricula for self-directed learning. This skill provides a structured approach to designing effective learning paths with clear objectives, milestones, resources, and assessment methods.

## Usage

When the user wants to create a learning program, follow this process:

### 1. Clarify Learning Goals
- What specific skills or knowledge does the user want to acquire?
- What is the target proficiency level (beginner, intermediate, advanced, expert)?
- What is the time horizon (weeks, months, year)?
- What are the success criteria / how will they know they've learned it?

### 2. Assess Current State
- What does the user already know?
- What are their learning preferences (reading, video, hands-on, projects)?
- How much time can they realistically dedicate per week?
- What constraints exist (budget, access to tools/environments, prerequisites)?

### 3. Design the Curriculum Structure
- **Break down into modules/units** - logical groupings of related concepts
- **Sequence logically** - prerequisites first, building toward complexity
- **Define learning objectives per module** - specific, measurable outcomes
- **Estimate time per module** - realistic based on user's weekly capacity

### 4. Select Resources
For each module, curate:
- Primary resources (1-2 core texts, courses, documentation)
- Supplementary resources (articles, videos, tutorials)
- Practice/exercise resources (projects, exercises, sandboxes)
- Community/discussion sources (forums, Discord, study groups)

### 5. Define Milestones & Assessments
- **Checkpoint assessments** - quick checks at end of each module
- **Capstone project** - synthesizes multiple modules
- **Self-assessment criteria** - rubrics or clear "definition of done"
- **Reflection prompts** - what worked, what didn't, adjustments needed

### 6. Create the Schedule
- Map modules to calendar weeks
- Build in buffer time (20% recommended)
- Schedule regular review sessions
- Plan for iteration/adjustment points

### 7. Output Format
Deliver the learning program as:
- **Overview document** - goals, structure, timeline
- **Module breakdown** - objectives, resources, time estimates
- **Weekly plan** - specific activities per week
- **Tracking template** - progress tracking, notes, adjustments
- **Resource list** - organized, with links and priority ratings

## Output Template

```markdown
# Learning Program: [Title]

## Goal
[Specific, measurable learning objective]

## Timeline
[Start date] - [End date] ([N] weeks)

## Weekly Commitment
[X] hours/week

## Modules

### Module 1: [Name] ([X] weeks)
**Objectives:**
- [Specific outcome 1]
- [Specific outcome 2]

**Resources:**
- Primary: [Resource with link]
- Supplementary: [Resource with link]
- Practice: [Exercise/project]

**Assessment:** [How to verify learning]

### Module 2: [Name] ([X] weeks)
...

## Milestones
- Week [N]: [Checkpoint description]
- Week [N]: [Capstone project due]

## Tracking
[Link to tracking template]
```

## Verification
After generating a program, verify:
- [ ] All modules have clear, measurable objectives
- [ ] Resources are accessible and appropriate level
- [ ] Timeline is realistic given weekly commitment
- [ ] Assessments actually measure the stated objectives
- [ ] Buffer time is included
- [ ] User has a way to track progress and adjust

## Notes
- Encourage the user to start with a pilot module before committing to the full program
- Build in regular retrospectives (every 2-3 weeks)
- The program should be a living document - adjust based on what works
