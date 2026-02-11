# ERD and EERD Automated Grading System - Project Overview

## Introduction

This project presents an automated grading system for Entity-Relationship Diagrams (ERDs) and Enhanced Entity-Relationship Diagrams (EERDs). The system uses large language models to evaluate student-created database diagrams and provide instant, detailed feedback. The goal is to reduce grading time from 15-20 minutes per diagram to under 10 seconds while maintaining grading quality comparable to human experts.

## Problem Statement

Manual ERD grading faces three critical challenges. First, it is time-consuming. Instructors spend 15-20 minutes per diagram, making large-class grading unsustainable. Second, it lacks consistency. Different graders apply different standards, and fatigue affects grading quality. Third, feedback is often delayed and minimal. Students wait 1-2 weeks for results and receive brief annotations without detailed explanations.

Automated assessment solves these problems by providing instant, consistent grading with comprehensive feedback at scale.

## System Architecture

The system uses a four-layer pipeline architecture:

**Layer 1: Presentation Layer** - A React-based web interface where students and instructors upload diagrams. The interface validates files, displays parsed results, and presents grading feedback in an organized format.

**Layer 2: Backend Orchestration Layer** - A Flask API that coordinates parsing and grading operations. It provides three main endpoints: `/api/convert` for diagram parsing, `/api/grade` for grading, and `/api/convert_to_structured` for JSON normalization.

**Layer 3: Diagram Parsing Layer** - Extracts structured data from SVG files exported from Draw.io. The parser identifies entities (regular, weak, associative), relationships (binary, ternary, n-ary), attributes (simple, key, multivalued, derived, composite), and inheritance hierarchies (disjoint, overlapping, union). It converts visual diagrams into structured JSON representations.

**Layer 4: LLM-Based Evaluation Layer** - Uses Google Gemini 2.0 Flash Lite to compare student submissions against instructor model answers. The layer employs "JSON prompting" - a structured prompting technique that encodes grading specifications, evaluation criteria, calibration examples, and output format constraints as JSON documents.

## Grading Methodology

The system implements two complementary grading approaches:

**Holistic Grading:** Compares the student's complete diagram against an instructor-provided model answer. The LLM evaluates similarity across five categories: entities (20 points), relationships (40 points), cardinalities (10 points), primary keys (20 points), and inheritance hierarchies (10 points). This approach handles naming variations and structural alternatives through semantic comparison.

**Schema-Based Grading:** Evaluates diagrams against a detailed rubric specifying required components. The system uses a 173-point evaluation schema for the HR Management System case study, checking each entity, relationship, attribute, and constraint individually. This approach provides transparent, fine-grained feedback showing exactly which components are correct, missing, or incorrect.

Both approaches award partial credit for partially correct components and generate natural language feedback explaining errors and suggesting improvements.

## Key Features

**Deterministic Grading:** The system configures the LLM with zero temperature and validates outputs to ensure identical diagrams receive identical scores across multiple grading runs. This reproducibility is critical for fairness in educational contexts.

**Semantic Equivalence Recognition:** The system recognizes semantically equivalent designs despite differences in naming or structure. For example, it awards credit for "Employee" when the model answer uses "Worker," and accepts both direct many-to-many relationships and decomposed associative entity representations.

**Comprehensive Feedback:** The system generates detailed reports identifying strengths, listing specific errors with explanations, noting missing components, and providing actionable improvement suggestions. Feedback is expressed in clear natural language accessible to database students.

**Fast Processing:** The system completes grading in under 10 seconds per submission, representing a 99%+ time reduction compared to manual grading. This enables instantaneous feedback delivery.

## Implementation Details

**Frontend:** Built with React 18.2 and Vite 4.x. Supports file upload, diagram visualization, and results display. Implements responsive design for desktop and tablet devices.

**Backend:** Python 3.11 with Flask 2.3.x. Handles API requests, file processing, and LLM communication. Uses the Google Gemini API for AI-based evaluation.

**Parsing:** Custom XML parser that extracts Draw.io metadata from SVG files. Identifies components through style attributes and connection analysis. Normalizes cardinality notations and serializes results to JSON.

**Grading Engine:** Constructs structured JSON prompts containing grading rules, calibration examples, model answer, and student submission. Sends prompts to Gemini with temperature=0 for deterministic outputs. Validates responses and recalculates scores for correctness.

## Evaluation Results

The system was evaluated on 42 student submissions from a database course. Key findings:

**Accuracy:** Achieved correlation of 0.89 with human expert grades and mean absolute error of 4.3 points on a 100-point scale. This demonstrates practical equivalence to human grading performance.

**Category Performance:** Entity grading achieved near-perfect accuracy. Relationship and inheritance grading faced greater challenges due to structural variation. Attribute and primary key grading showed strong performance.

**Efficiency:** Average grading time was 8.2 seconds per submission. This enables truly instantaneous feedback for students.

**Consistency:** The system produced identical scores for identical diagrams across multiple runs, confirming deterministic behavior.

## Research Contributions

**Architectural Contribution:** A modular pipeline that transforms visual diagrams into machine-gradeable representations while preserving semantic fidelity. The four-layer design separates concerns and enables independent testing and enhancement.

**Methodological Contribution:** The JSON prompting technique provides structured, unambiguous task specifications that improve grading consistency. The approach demonstrates how LLMs can perform complex evaluation tasks requiring domain knowledge and semantic reasoning.

**Empirical Contribution:** Comprehensive evaluation establishing the feasibility of LLM-based ERD grading with accuracy approaching human expert performance. The study identifies strengths and limitations across different assessment categories.

**Practical Contribution:** A working system suitable for real educational deployment. The web interface, error handling, and feedback generation make the system immediately usable in database courses.

## Limitations and Future Work

**Current Limitations:** The system requires SVG files with embedded Draw.io metadata, excluding hand-drawn diagrams. It assumes a single reference solution, limiting applicability in open-ended design scenarios. The grading rubric uses fixed categories requiring JSON editing for extensive customization.

**Future Extensions:** Planned improvements include support for hand-drawn diagrams through computer vision, multi-reference grading for open-ended tasks, expanded notation support for other diagramming tools (yEd, Lucidchart, Visio), and conversational AI for interactive explanations of grading results.

**Broader Vision:** The approach should generalize to other diagram types including UML class diagrams, database schemas, data flow diagrams, and sequence diagrams. The core architecture of parsing, structured representation, and LLM-based evaluation transfers with appropriate domain-specific adaptations.

## Conclusion

This project demonstrates that automated ERD grading using large language models can achieve accuracy approaching human expert performance while delivering feedback instantaneously at negligible cost. The system addresses real educational challenges by reducing instructor workload, improving grading consistency, and providing detailed formative feedback that supports student learning.

The success of this approach shows the potential for AI-augmented educational assessment to enhance rather than replace human instruction. By handling time-consuming grading tasks, the system frees instructors to focus on curriculum design, student mentoring, and enriched learning experiences.

The JSON prompting technique, deterministic grading strategies, and multi-perspective evaluation framework provide replicable templates for automated assessment in other domains involving complex visual artifacts, open-ended design tasks, and semantic reasoning requirements.
