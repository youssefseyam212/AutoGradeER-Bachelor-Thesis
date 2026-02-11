"""
JSON Prompting approach for ERD grading.
Uses structured data instead of conversational prompts for better accuracy.
"""

import json


def generate_grade_explanation(grade, entities_with_pk, total_entities, total_relationships):
    """
    Generate a human-readable explanation for why a submission received a particular grade.
    """
    if grade == 100:
        return "Perfect submission - all entities, relationships, and cardinalities are correct with no errors"
    elif grade >= 95:
        return f"Excellent work - nearly perfect with only 1-2 very minor issues (e.g., slight notation differences). {entities_with_pk}/{total_entities} entities have PKs, {total_relationships} relationships present"
    elif grade >= 90:
        return f"Very good work - missing 1-2 relationships or minor cardinality issues. {entities_with_pk}/{total_entities} entities have PKs, {total_relationships} relationships present"
    elif grade >= 80:
        return f"Good work but missing several relationships or some cardinality errors. {entities_with_pk}/{total_entities} entities have PKs, {total_relationships} relationships present"
    elif grade >= 70:
        return f"Acceptable but with noticeable gaps - multiple missing relationships and errors. {entities_with_pk}/{total_entities} entities have PKs, {total_relationships} relationships present"
    else:
        return f"Poor work - many missing relationships and fundamental errors. {entities_with_pk}/{total_entities} entities have PKs, {total_relationships} relationships present"


def create_json_prompt(teacher_erd, student_erd, custom_requirements=None):
    """
    Create a structured JSON prompt for ERD grading.

    This uses "JSON prompting" - structured data format for clear, deterministic instructions.
    Like giving code to a computer, not chatting with a friend.
    """

    with open('training_dataset.json', 'r') as f:
        training_data = json.load(f)

    all_examples = training_data['examples']

   
    sorted_examples = sorted(all_examples, key=lambda x: x['grade'], reverse=True)

    
    selected_indices = []

    # Strategy: get 1-2 examples from different grade brackets
    for grade_bracket in [(100, 100), (90, 99), (75, 89)]:
        min_g, max_g = grade_bracket
        for ex in sorted_examples:
            if min_g <= ex['grade'] <= max_g and ex not in [all_examples[i] for i in selected_indices]:
                selected_indices.append(all_examples.index(ex))
                break

    # Initialize reference_examples list
    reference_examples = []

    # Build reference examples with full ERD data for few-shot learning
    for idx in selected_indices[:1]:  # Use only 1 example (best) to reduce noise
        ex = all_examples[idx]

        # Count PKs
        entities_with_pk = sum(1 for e in ex['erd']['entities']
                              if any(attr.get('type') == 'key' for attr in e['attributes']))

        # Count metrics for comparison analysis
        student_entities_count = len(ex['erd']['entities'])
        student_relationships_count = len(ex['erd']['relationships'])
        student_inheritances_count = len(ex['erd'].get('inheritances', []))

        reference_examples.append({
            "team_name": ex['team_name'],
            "grade": ex['grade'],
            "entities_count": student_entities_count,
            "relationships_count": student_relationships_count,
            "inheritances_count": student_inheritances_count,
            "entities_with_pk": entities_with_pk,
            "status": ex['status'],
            # Add grade breakdown based on grade
            "breakdown": calculate_breakdown_from_grade(ex['grade'], student_relationships_count),
            # Detailed comparison analysis (removed full ERD to reduce tokens)
            "comparison_analysis": {
                "entities_present": f"{entities_with_pk}/{student_entities_count} entities have primary keys",
                "relationships_present": f"{student_relationships_count} relationships total",
                "quality_indicators": {
                    "has_primary_keys": entities_with_pk > 0,
                    "has_relationships": student_relationships_count > 0,
                    "has_inheritance": student_inheritances_count > 0,
                    "pk_coverage_percentage": round((entities_with_pk / student_entities_count * 100) if student_entities_count > 0 else 0, 1)
                },
                "why_this_grade": generate_grade_explanation(ex['grade'], entities_with_pk, student_entities_count, student_relationships_count)
            }
        })

    # Create structured prompt
    json_prompt = {
        "task": "grade_erd_submission",
        "instructions": {
            "mode": "semantic_equivalence",
            "philosophy": "human_teacher_not_robot",
            "primary_focus": "relationship_correctness",
            "CRITICAL_FIRST_STEP": "BEFORE grading, verify BOTH ERDs model the SAME business domain. Learning platform ≠ HR management. School = University (both education). If different domains → System match: NO.",
            "CONSISTENCY_REQUIREMENT": "You MUST be CONSISTENT. Grading the same ERD multiple times MUST produce the SAME score. Use the reference examples to calibrate your grading accurately and consistently."
        },
        "REASONING_FRAMEWORK": {
            "YOU_ARE_A_TEACHER_NOT_A_ROBOT": {
                "mindset": "Think like an experienced database professor, not a strict comparison algorithm",
                "approach": "Use judgment and reasoning, not just pattern matching",
                "core_principle": "If student's approach makes logical sense and serves the system requirements, it deserves full credit even if different from model answer"
            },
            "CRITICAL_THINKING_STEPS": {
                "step_1_understand_student_intent": "What is the student trying to model? What business logic are they representing?",
                "step_2_evaluate_correctness": "Does their approach correctly capture the system requirements and relationships?",
                "step_3_compare_with_model": "How does it differ from model answer? Are differences superficial or fundamental?",
                "step_4_apply_judgment": "Would a real teacher accept this? Does it demonstrate understanding?",
                "step_5_decide_score": "Give credit for correctness and understanding, not just exact matching"
            },
            "REASONING_EXAMPLES": {
                "example_1": {
                    "situation": "Model answer has 'Student enrolls in Course (M:N)'. Student has 'Student takes Course (M:N)' plus 'Enrollment' associative entity with attributes.",
                    "reasoning": "Student's approach is actually MORE sophisticated - they recognized the M:N needs an associative entity. This is BETTER than model answer.",
                    "decision": "FULL CREDIT + note in feedback that this is excellent modeling"
                },
                "example_2": {
                    "situation": "Model has User->Admin,Customer inheritance. Student has separate Admin and Customer entities with same attributes.",
                    "reasoning": "Both approaches work. Inheritance is more elegant, but separate entities are simpler and equally valid. Student may have valid reasons (simplicity, avoiding inheritance complexity).",
                    "decision": "FULL CREDIT - this is a design choice, not an error"
                },
                "example_3": {
                    "situation": "Model has Employee (1:M) Department. Student has Employee (1:1) Department.",
                    "reasoning": "This is a real difference. One employee in multiple departments vs one department. This changes business logic significantly.",
                    "decision": "DEDUCT POINTS - this is an actual modeling error that affects system behavior"
                }
            },
            "WHEN_TO_ACCEPT_DIFFERENCES": {
                "ACCEPT_FULL_CREDIT": [
                    "Different names but same meaning (enrolls vs takes)",
                    "Different structure but same outcome (inheritance vs separate entities)",
                    "Student's approach is more detailed/sophisticated than model",
                    "Alternative valid interpretation of requirements",
                    "Different cardinality notation but same meaning (M vs N vs *)"
                ],
                "MINOR_DEDUCTION": [
                    "Slightly different interpretation that still makes business sense",
                    "Missing minor relationship that doesn't break core logic",
                    "Using weaker entity where strong entity could work (but weak is acceptable)"
                ],
                "MAJOR_DEDUCTION": [
                    "Cardinality that violates business rules (1:1 when should be 1:M)",
                    "Missing critical relationships that break system logic",
                    "Wrong entities connected (fundamentally different relationship)",
                    "Missing primary keys on regular entities"
                ]
            }
        },
        "grading_config": {
            "total_points": 100,
            "breakdown": {
                "entities": {
                    "points": 20,
                    "criteria": "key_entities_present",
                    "allow_name_variations": True
                },
                "relationships": {
                    "points": 40,
                    "criteria": "semantically_correct_and_complete",
                    "primary_focus": True,
                    "CRITICAL_MATCHING_RULES": {
                        "relationship_name_different_but_same_entities_and_cardinality": {
                            "rule": "If entities connected are same AND cardinalities are same → FULL CREDIT even if relationship name differs",
                            "example": "Teacher: 'enrolls' (Student 1:M Course), Student: 'takes' (Student 1:M Course) → SAME relationship, FULL CREDIT",
                            "score": "full_credit"
                        },
                        "matching_criteria": {
                            "step_1": "Compare entities connected (allow semantic equivalents like Customer=Client)",
                            "step_2": "Compare cardinalities (allow equivalent notations: M=N=*, 1=1..1)",
                            "step_3": "Check if serves same system flow/business logic",
                            "if_all_match": "FULL CREDIT regardless of relationship name difference"
                        },
                        "when_relationship_is_truly_different": {
                            "different_entities_connected": "this is actually a different relationship",
                            "different_cardinality": "mark as incorrect cardinality, deduct from cardinality section",
                            "missing_relationship_entirely": "deduct from relationships score"
                        }
                    },
                    "SEMANTIC_EQUIVALENCE_EXAMPLES": {
                        "enrolls_takes_registers": "all mean Student-Course relationship",
                        "works_for_employed_by": "all mean Employee-Company relationship",
                        "orders_purchases_buys": "all mean Customer-Product relationship",
                        "owns_has_possesses": "all mean ownership relationship"
                    }
                },
                "cardinalities": {
                    "points": 10,
                    "criteria": "reflects_business_rules",
                    "accept_equivalents": True
                },
                "primary_keys": {
                    "points": 20,
                    "criteria": "entities_have_pks",
                    "CRITICAL_GRADING_RULES": {
                        "what_to_check": "Every regular entity MUST have at least one primary key attribute",
                        "weak_entities": "Weak entities may have partial keys only - this is acceptable",
                        "associative_entities": "Associative entities typically derive PKs from relationships - acceptable",
                        "missing_pks": "List SPECIFIC entities that are missing primary keys",
                        "incorrect_pks": "List cases where PK designation is wrong (e.g., composite key should be simple, or wrong attribute marked as PK)"
                    },
                    "required_feedback": {
                        "missing": "List entities without PKs (e.g., 'Student, Course, Department')",
                        "incorrect": "List specific PK errors if any (e.g., 'Employee: SSN should be PK but marked as regular')"
                    }
                },
                "inheritance": {
                    "points": 10,
                    "criteria": "functional_equivalence_not_structural_match",
                    "CRITICAL_INSTRUCTION": "READ THIS CAREFULLY - Inheritance grading is EXTREMELY LENIENT",
                    "grading_philosophy": "Both inheritance and separate entities are valid if they serve the same system flow and business logic. Different design choices are EQUALLY VALID.",
                    "MANDATORY_RULES_FOLLOW_EXACTLY": {
                        "RULE_1_BOTH_HAVE_ZERO_INHERITANCE": {
                            "condition": "teacher_erd.inheritances is empty AND student_erd.inheritances is empty",
                            "action": "MUST give 10/10 points - NO EXCEPTIONS",
                            "score": "10/10"
                        },
                        "RULE_2_TEACHER_HAS_INHERITANCE_STUDENT_HAS_INHERITANCE": {
                            "condition": "both have inheritance hierarchies",
                            "if_same_structure": "10/10 full_credit",
                            "if_different_but_serves_same_flow": "10/10 full_credit",
                            "if_different_type_disjoint_vs_overlapping": "9/10 minor_difference_only",
                            "default": "8-10/10 unless logically wrong"
                        },
                        "RULE_3_TEACHER_HAS_INHERITANCE_STUDENT_USES_SEPARATE_ENTITIES": {
                            "condition": "teacher uses inheritance (e.g., User->Admin,Customer), student uses separate entities (Admin, Customer as standalone)",
                            "action": "MUST give 10/10 if separate entities serve the same system flow",
                            "score": "10/10",
                            "explanation": "This is a VALID alternative design choice. Example: Teacher models User with Admin and Customer subtypes. Student models Admin and Customer as separate entities. BOTH ARE CORRECT if they achieve the same functionality.",
                            "CRITICAL": "DO NOT PENALIZE for choosing separate entities over inheritance"
                        },
                        "RULE_4_STUDENT_HAS_INHERITANCE_TEACHER_USES_SEPARATE_ENTITIES": {
                            "condition": "student uses inheritance, teacher uses separate entities",
                            "action": "MUST give 10/10 - student chose better design",
                            "score": "10/10",
                            "explanation": "Inheritance might be a superior modeling choice. DO NOT PENALIZE."
                        },
                        "RULE_5_WHEN_TO_DEDUCT_POINTS": {
                            "ONLY_deduct_if": [
                                "inheritance hierarchy is logically incorrect (wrong parent-child relationship)",
                                "inheritance type (disjoint/overlapping) violates business constraints",
                                "missing inheritance causes loss of critical business logic"
                            ],
                            "DO_NOT_deduct_if": [
                                "student chose separate entities instead of inheritance",
                                "student chose inheritance instead of separate entities",
                                "different but valid grouping of subtypes",
                                "minor differences in inheritance structure"
                            ]
                        }
                    },
                    "SCORING_FORMULA": {
                        "both_have_zero": "10/10 ALWAYS",
                        "both_match_exactly": "10/10 ALWAYS",
                        "different_valid_approaches": "10/10 DEFAULT",
                        "minor_structural_difference": "9/10",
                        "only_deduct_significantly_if_logically_wrong": "5-8/10"
                    },
                    "key_principle": "DEFAULT TO 10/10 unless student's approach is PROVABLY INCORRECT. Inheritance is subjective - err on the side of giving full credit."
                }
            }
        },
        "grading_rules": {
            "semantic_matching": {
                "enabled": True,
                "CRITICAL_INSTRUCTION": "Match by MEANING and FUNCTION, not just exact names",
                "relationship_matching_algorithm": {
                    "step_1": "For each teacher relationship, find student relationships connecting the same entities (allow semantic name equivalents)",
                    "step_2": "Compare cardinalities using equivalent notations",
                    "step_3": "If entities + cardinalities match, consider it CORRECT even if relationship name differs",
                    "step_4": "Only mark as incorrect if: (a) entities are different, (b) cardinality is wrong, or (c) relationship completely missing"
                },
                "examples": {
                    "equivalent_entity_names": ["Customer = Client", "Learner = Student", "Course = Class", "Employee = Worker = Staff"],
                    "equivalent_relationship_names": ["enrolls = takes = registers", "works_for = employed_by", "orders = purchases = buys"],
                    "equivalent_cardinalities": {
                        "many": ["M", "N", "*", "0..*", "1..*"],
                        "one": ["1", "1..1", "E O", "EO", "EXACTLY ONE"],
                        "optional_one": ["0..1"]
                    }
                },
                "MATCHING_PRIORITY": {
                    "1_HIGHEST": "Same entities connected + same cardinality = CORRECT (ignore name difference)",
                    "2_MEDIUM": "Same entities + slightly different cardinality = minor deduction",
                    "3_LOW": "Different entities or completely missing = major deduction"
                }
            },
            "ternary_relationships": {
                "CRITICAL_INSTRUCTION": "Ternary relationships are preserved as-is (NO splitting into binary)",
                "handling": "treat_as_single_relationship",
                "relationship_type_field": "relationship_type='ternary'",
                "matching_rules": {
                    "ternary_vs_ternary": {
                        "rule": "Compare all three participants and their cardinalities",
                        "full_credit_if": "Same three entities connected (allow semantic equivalents)",
                        "example": "Teacher: Teaching(Instructor[1], Course[M], Student[M]), Student: Teaches(Professor[1], Class[M], Learner[M]) → FULL CREDIT if semantically equivalent"
                    },
                    "ternary_vs_binary_decomposition": {
                        "rule": "If teacher has ternary and student decomposed into multiple binary relationships connecting the same entities",
                        "action": "Accept as valid alternative modeling approach - FULL CREDIT",
                        "example": "Teacher: Works_On(Employee, Project, Department) ternary. Student: three binaries (Employee-Project, Employee-Department, Project-Department) → FULL CREDIT",
                        "reasoning": "Decomposing ternary into binaries is a valid database design choice"
                    },
                    "binary_decomposition_vs_ternary": {
                        "rule": "If teacher has binary decomposition and student uses proper ternary",
                        "action": "Student shows BETTER understanding - FULL CREDIT with bonus praise",
                        "example": "Student recognized three-way relationship and modeled as ternary instead of separate binaries → EXCELLENT",
                        "reasoning": "Ternary relationships are the proper way to model three-way dependencies"
                    },
                    "participant_matching": {
                        "step_1": "Extract all participants from ternary relationship",
                        "step_2": "Match each participant entity (allow semantic equivalents like Teacher=Instructor)",
                        "step_3": "Compare cardinalities for each participant",
                        "step_4": "If all three participants + cardinalities match → FULL CREDIT"
                    }
                },
                "grading_philosophy": {
                    "ternary_is_advanced": "Using ternary relationships demonstrates advanced database knowledge",
                    "both_approaches_valid": "Ternary relationship OR decomposition into binaries are both correct",
                    "encourage_ternary": "If student uses ternary correctly, praise this in feedback",
                    "do_not_penalize": "Never penalize for choosing ternary vs binary or vice versa - both are valid design choices"
                },
                "examples_of_ternary_relationships": {
                    "example_1": {
                        "name": "Teaching",
                        "participants": ["Instructor[1]", "Course[M]", "Student[M]"],
                        "meaning": "An instructor teaches a course to students",
                        "why_ternary": "The relationship only makes sense with all three entities together"
                    },
                    "example_2": {
                        "name": "Supply",
                        "participants": ["Supplier[M]", "Part[M]", "Project[M]"],
                        "meaning": "Supplier supplies parts to projects",
                        "why_ternary": "Cannot decompose without losing context (which supplier supplies which part to which project)"
                    },
                    "example_3": {
                        "name": "Works_On",
                        "participants": ["Employee[M]", "Project[M]", "Department[M]"],
                        "meaning": "Employee from department works on project",
                        "why_ternary": "Captures three-way dependency"
                    }
                },
                "CRITICAL_SCORING_RULES": {
                    "teacher_ternary_student_ternary_match": "FULL CREDIT (40/40 for relationship)",
                    "teacher_ternary_student_binary_decomposition": "FULL CREDIT - valid alternative",
                    "teacher_binary_student_ternary": "FULL CREDIT + praise - student showed better understanding",
                    "teacher_ternary_student_missing": "DEDUCT - missing critical relationship",
                    "teacher_ternary_student_wrong_participants": "DEDUCT - wrong entities connected"
                }
            },
            "flexible_grading": {
                "different_structure_same_outcome": "full_credit",
                "minor_name_differences": "full_credit",
                "alternative_valid_approaches": "full_credit",
                "RELATIONSHIP_NAME_DIFFERS_BUT_SAME_CONNECTION": {
                    "rule": "MUST give full credit if relationship connects same entities with same cardinality",
                    "explanation": "Different relationship names are acceptable as long as the connection (entities + cardinality) is identical",
                    "example": "Teacher: 'manages' (Manager 1:M Employee), Student: 'supervises' (Manager 1:M Employee) → FULL CREDIT",
                    "action": "Do NOT list in 'incorrectRelationships' - list in 'correctRelationships' instead"
                }
            },
            "deduction_policy": {
                "missing_relationships": "major_deduction - only if relationship is completely absent",
                "wrong_cardinality": "moderate_deduction - only if cardinality is actually different (not just different notation)",
                "missing_entities": "smaller_deduction",
                "missing_pks": "moderate_deduction",
                "IMPORTANT_DO_NOT_DEDUCT_FOR": [
                    "relationship name differences when entities and cardinality match",
                    "entity name differences when semantically equivalent (Customer=Client)",
                    "cardinality notation differences when semantically same (M=N=*)",
                    "different but valid design choices (inheritance vs separate entities)"
                ],
                "ONLY_DEDUCT_FOR_ACTUAL_ERRORS": {
                    "completely_missing_relationship": "deduct from relationships score",
                    "wrong_entities_connected": "deduct from relationships score",
                    "wrong_cardinality_value": "deduct from cardinalities score (NOT relationships)",
                    "missing_primary_keys": "deduct from primary_keys score (NOT entities)"
                }
            }
        },
        "reference_calibration": {
            "description": "Use these real examples to calibrate your grading",
            "CRITICAL_INSTRUCTION": "Each example below contains FULL ERD DATA (entities, relationships, inheritances). Study the actual ERD content to understand what quality corresponds to each grade level.",
            "how_to_use_examples": {
                "step_1": "Look at the full_erd field for each example - this shows the actual ERD data",
                "step_2": "Compare the student submission you're grading to these full ERD examples",
                "step_3": "Count missing/incorrect items in student submission vs these examples",
                "step_4": "Match the error pattern to the closest reference example",
                "step_5": "Assign a grade similar to that reference example"
            },
            "examples": reference_examples,
            "patterns": {
                "perfect_100": {
                    "characteristics": "all_entities_all_relationships_correct_all_cardinalities_accurate",
                    "example": "talk tuah enjoyers",
                    "actual_grade": 100.0,
                    "key_point": "This is the gold standard - no errors whatsoever"
                },
                "excellent_95_99": {
                    "characteristics": "1_2_minor_issues_tiny_cardinality_variations",
                    "example": "top 1",
                    "actual_grade": 98.5,
                    "key_point": "Nearly perfect - only 1-2 very minor issues like slight cardinality notation differences"
                },
                "good_90_94": {
                    "characteristics": "missing_1_2_relationships_or_few_cardinality_errors",
                    "example": "MR.J's",
                    "actual_grade": 93.0,
                    "key_point": "Very good work - missing 1-2 relationships but most are correct"
                },
                "acceptable_75_89": {
                    "characteristics": "missing_several_relationships_some_cardinality_errors",
                    "example": "AEA",
                    "actual_grade": 79.5,
                    "key_point": "Acceptable but with noticeable gaps - missing multiple relationships"
                },
                "poor_below_75": {
                    "characteristics": "missing_many_relationships_many_errors",
                    "example": "Lynx",
                    "actual_grade": 73.5,
                    "key_point": "Poor work - many missing relationships and fundamental errors"
                }
            },
            "CRITICAL_ACCURACY_CALIBRATION": {
                "instruction": "Use the reference examples above to CALIBRATE your grading accurately",
                "DO_NOT_over_inflate_scores": "If submission has many missing relationships like 'Lynx', it should be around 73-75, NOT 84+",
                "DO_NOT_under_score_excellent_work": "If submission is nearly perfect like 'top 1', it should be 95-99, NOT 88-92",
                "comparison_method": "Compare the number of missing/incorrect relationships in student submission to reference examples to determine appropriate grade range"
            }
        },
        "model_answer": {
            "description": "Teacher's ERD (correct solution)",
            "data": teacher_erd
        },
        "student_submission": {
            "description": "Student's ERD to be graded",
            "data": student_erd
        },
        "custom_requirements": custom_requirements if custom_requirements else None,
        "GRADING_MINDSET": {
            "BEFORE_YOU_START": {
                "question_1": "Does the student's ERD demonstrate understanding of database concepts?",
                "question_2": "Would this ERD work in a real system?",
                "question_3": "Are the differences just stylistic or truly wrong?",
                "question_4": "If I were teaching this class, would I mark this as incorrect?"
            },
            "DEFAULT_ASSUMPTION": "Student is correct unless proven otherwise",
            "BENEFIT_OF_DOUBT": "When in doubt between two scores, choose the HIGHER score - BUT be accurate and fair, not overly generous",
            "CALIBRATION_REQUIREMENT": {
                "perfect_100": "ONLY if ALL entities, ALL relationships, ALL cardinalities are correct",
                "excellent_95_99": "Nearly perfect, 1-2 very minor issues. USE THIS RANGE - do not hesitate to give 95-99 for nearly perfect work",
                "good_90_94": "Very good work, missing 1-2 relationships or minor cardinality issues",
                "acceptable_80_89": "Good work but missing several relationships or cardinality errors",
                "needs_improvement_70_79": "Multiple missing relationships, many errors",
                "poor_below_70": "Many critical missing relationships, fundamental errors",
                "IMPORTANT_DO_NOT_UNDER_SCORE": "If submission is nearly perfect, it MUST be in 95-99 range, not 88-92"
            },
            "PRAGMATIC_APPROACH": {
                "focus_on": "Does it work? Does it make sense? Does it capture the business logic?",
                "dont_focus_on": "Is it pixel-perfect identical to model answer?",
                "remember": "There are often MULTIPLE correct ways to model the same system"
            },
            "FORBIDDEN_ACTIONS": [
                "NEVER deduct points just because student chose different naming",
                "NEVER penalize valid alternative approaches",
                "NEVER require exact structural match when semantic equivalence exists",
                "NEVER ignore the business logic when comparing relationships"
            ],
            "ENCOURAGED_ACTIONS": [
                "ALWAYS consider if student's approach is logically sound",
                "ALWAYS give credit for valid alternative solutions",
                "ALWAYS think 'would a real teacher accept this?'",
                "ALWAYS look at the BIG PICTURE not just individual elements"
            ]
        },
        "STEP_BY_STEP_GRADING_WORKFLOW": {
            "STEP_0_SYSTEM_ALIGNMENT_CHECK": {
                "action": "FIRST verify both ERDs model the SAME SYSTEM - look at main entities to identify the domain",
                "identify_domains": {
                    "teacher_domain": "Look at teacher ERD main entities - what is the business/system domain? (e.g., education/school, healthcare/hospital, e-commerce/shopping, HR/employee management, banking/finance, travel/tourism, library, hotel, etc.)",
                    "student_domain": "Look at student ERD main entities - what is the business/system domain?",
                    "compare": "Are these the SAME business domain? Learning platform vs HR management = DIFFERENT. School vs University = SAME. Hospital vs Clinic = SAME."
                },
                "set_correctnessAnalysis": {
                    "if_same": "System match: YES. Both model [domain] system",
                    "if_different": "System match: NO. Teacher: [domain], Student: [different domain]"
                },
                "CRITICAL_EXAMPLES": {
                    "MATCH_YES": "Teacher: school system (Student, Course, Teacher) + Student: university system (Learner, Class, Professor) → YES, both education",
                    "MATCH_NO": "Teacher: learning platform (Learner, Course) + Student: HR system (Employee, Department) → NO, different domains",
                    "MATCH_NO_2": "Teacher: hospital (Patient, Doctor) + Student: travel agency (Passenger, Flight) → NO, different domains"
                },
                "GRADING_NOTE": "If systems don't match, grade the ERD normally. The system will automatically apply a 20-point penalty in post-processing."
            },
            "STEP_1_ANALYZE_STUDENT_ERD": {
                "action": "Read and understand the student's ERD completely",
                "ask_yourself": "What system is this modeling? What are the key business rules?"
            },
            "STEP_2_COMPARE_ENTITIES": {
                "action": "Match student entities to model entities",
                "use_reasoning": "Are 'Customer' and 'Client' the same thing? Yes → MATCH",
                "give_credit_for": "Semantic equivalence, not just exact names"
            },
            "STEP_3_COMPARE_RELATIONSHIPS": {
                "action": "For EACH model relationship, find corresponding student relationship",
                "matching_algorithm": "Look at entities connected + cardinality, NOT just relationship name",
                "reasoning_example": "Model: 'enrolls' (Student M:N Course). Student: 'takes' (Student M:N Course). Ask: Do they connect the same entities? Yes. Same cardinality? Yes. CONCLUSION: These are the SAME relationship. FULL CREDIT.",
                "CRITICAL_DO_NOT_MARK_AS_MISSING": "If student has a relationship with SAME entities connected + SAME cardinality but DIFFERENT name → This is NOT missing. This is CORRECT. Student just named it differently. Example: Teacher has 'enrolls', Student has 'registers' → BOTH connect Student-Course with M:N → NOT MISSING, it's PRESENT with different name.",
                "critical_rule": "If entities + cardinality match, relationship is CORRECT regardless of name",
                "SPECIAL_CASE_TERNARY_RELATIONSHIPS": {
                    "detection": "Check relationship_type field - if 'ternary', this is a three-way relationship",
                    "matching": "Compare all three participants (entities) and their cardinalities",
                    "example": "Teacher: Teaching(Instructor[1], Course[M], Student[M]) ternary. Student: Teaching(Teacher[1], Class[M], Learner[M]) ternary. MATCH if semantically equivalent.",
                    "alternative_valid": "If teacher has ternary but student decomposed into multiple binaries connecting same entities → FULL CREDIT",
                    "critical_rule": "Ternary and binary decomposition are BOTH valid - don't penalize either approach"
                }
            },
            "STEP_4_EVALUATE_CARDINALITIES": {
                "action": "Check if cardinalities make business sense",
                "reasoning": "Does '1:M' vs 'M:N' change the business logic? If yes, it matters. If student used M, N, or * - these are ALL 'many'.",
                "dont_penalize": "Different notation for same meaning (M=N=*=0..*=1..*)"
            },
            "STEP_5_CHECK_PRIMARY_KEYS": {
                "action": "Check EACH entity for primary key attributes",
                "required_output": {
                    "missing_pks": "List specific entity names that lack primary keys (e.g., 'Student, Course, Department')",
                    "incorrect_pks": "List specific PK designation errors if any (e.g., 'Employee has wrong PK' or 'None' if all correct)",
                    "format": "primaryKeyAnalysis: 'Missing PKs: [entities] | Incorrect: [details or None]'"
                },
                "scoring_rules": {
                    "all_entities_have_correct_pks": "20/20 points",
                    "1_2_missing_pks": "deduct 4-8 points",
                    "3_5_missing_pks": "deduct 10-14 points",
                    "more_than_5_missing": "deduct 16-20 points"
                },
                "CRITICAL": "Be SPECIFIC about which entities are missing PKs - don't just say 'some entities missing PKs'"
            },
            "STEP_6_CHECK_INHERITANCE": {
                "action": "Apply the MANDATORY_RULES_FOLLOW_EXACTLY from inheritance section",
                "default_score": "10/10 unless student's approach is provably wrong",
                "remember": "Separate entities vs inheritance are BOTH valid - don't penalize design choices"
            },
            "STEP_7_FINAL_REASONING": {
                "action": "Look at overall ERD quality and correctness",
                "ask_yourself": "If this student came to my office hours, would I say 'this is wrong' or 'this is good work'?",
                "principle": "Grade based on UNDERSTANDING and CORRECTNESS, not SIMILARITY to model answer",
                "CRITICAL_CONSISTENCY_RULES": {
                    "rule_1": "If relationship connects SAME entities with SAME cardinality → CORRECT (even if name differs)",
                    "rule_2": "Count errors OBJECTIVELY: missing PK = specific deduction, missing relationship = specific deduction",
                    "rule_3": "SAME errors MUST result in SAME score EVERY TIME",
                    "rule_4": "Calculate breakdown FIRST (entities + relationships + cardinalities + PKs + inheritance), THEN set final score"
                },
                "final_calibration_check": {
                    "step_1": "Count how many relationships are TRULY missing (not just renamed)",
                    "step_2": "Count how many entities are missing primary keys",
                    "step_3": "Calculate breakdown scores based on these EXACT counts",
                    "step_4": "Verify breakdown adds up to final score (entities/20 + relationships/40 + cardinalities/10 + primaryKeys/20 + inheritance/10 = total/100)",
                    "step_5": "BE CONSISTENT - grading same ERD must give same score"
                }
            }
        },
        "output_specification": {
            "format": "json",
            "required_fields": {
                "score": "string in format XX/100",
                "analysis": {
                    "correctnessAnalysis": "string (Format: 'System match: [YES/NO]. Teacher: [domain], Student: [domain]', max 100 chars. ALWAYS include this field FIRST before grading)",
                    "correctEntities": "string (BRIEF summary with count only, max 50 chars)",
                    "missingEntities": "string (list ONLY TOP 3-5 most critical, max 100 chars)",
                    "correctRelationships": "string (count only, e.g. '19/33 relationships correct', max 50 chars)",
                    "incorrectRelationships": "string (list ONLY TOP 3-5 most critical issues, max 150 chars)",
                    "missingRelationships": "string (list ONLY TOP 3-5 most critical, max 150 chars)",
                    "primaryKeyAnalysis": "string (Format: 'Missing PKs: Entity1, Entity2 | Incorrect: details' max 200 chars)",
                    "inheritanceAnalysis": "string (BRIEF summary, max 80 chars)",
                    "cardinalityAnalysis": "string (BRIEF summary, max 80 chars)"
                },
                "breakdown": {
                    "entities": "XX/20",
                    "relationships": "XX/40",
                    "cardinalities": "XX/10",
                    "primaryKeys": "XX/20",
                    "inheritance": "XX/10"
                },
                "feedback": {
                    "strengths": "string (max 150 chars)",
                    "errors": "string (max 150 chars)",
                    "missing": "string (max 150 chars)"
                },
                "suggestions": "array of strings max 5, each suggestion max 100 chars"
            },
            "validation": {
                "breakdown_sum_must_equal_score": True,
                "all_fields_must_be_strings_except_suggestions": True,
                "suggestions_max_length": 100,
                "CRITICAL_LENGTH_LIMITS": "ALL analysis fields must be kept SHORT to prevent JSON truncation errors. Focus on counts and top issues only."
            },
            "CRITICAL_INSTRUCTION_AVOID_JSON_ERRORS": {
                "rule": "Keep ALL string fields SHORT and CONCISE",
                "why": "Long strings cause JSON parsing errors and break the grading system",
                "examples": {
                    "GOOD_missingEntities": "Top issues: Learners, Courses, Modules (20 more entities missing)",
                    "BAD_missingEntities": "Learners, Courses, Modules, Learning Activities, Course Enrollment, Achievements, Badges, Leaderboards, Learning Paths, Interaction Logs...",
                    "GOOD_incorrectRelationships": "3 key issues: Learner-Course cardinality, missing Module-Activity, wrong Quest-Reward",
                    "BAD_incorrectRelationships": "Missing or incorrect relationships between Learners and Courses, Learners and Badges, Courses and Modules...",
                    "GOOD_primaryKeyAnalysis": "Missing PKs: Student, Course, Department | Incorrect: None",
                    "ALSO_GOOD_primaryKeyAnalysis": "Missing PKs: None | Incorrect: Employee (age marked as PK instead of empID)",
                    "BAD_primaryKeyAnalysis": "Some entities are missing primary keys and there are some issues with PK designation"
                },
                "mandatory_format": "For lists: mention top 3-5 items + count of remaining (e.g., 'Entity1, Entity2, Entity3 (15 more missing)')"
            }
        }
    }

    return json_prompt


def calculate_breakdown_from_grade(grade, relationship_count):
    """Estimate breakdown based on total grade (for reference examples)."""
    if grade == 100:
        return {"entities": "20/20", "relationships": "40/40", "cardinalities": "10/10", "primaryKeys": "20/20", "inheritance": "10/10"}
    elif grade >= 98:
        return {"entities": "20/20", "relationships": "38.5/40", "cardinalities": "10/10", "primaryKeys": "20/20", "inheritance": "10/10"}
    elif grade >= 90:
        lost = 100 - grade
        return {"entities": "20/20", "relationships": f"{40-lost}/40", "cardinalities": "10/10", "primaryKeys": "20/20", "inheritance": "10/10"}
    elif grade >= 75:
        # Distribute losses across entities, relationships, cardinalities
        lost = 100 - grade
        rel_loss = int(lost * 0.6)  # 60% of loss in relationships
        card_loss = int(lost * 0.15)  # 15% in cardinalities
        ent_loss = int(lost * 0.25)  # 25% in entities
        return {
            "entities": f"{20-ent_loss}/20",
            "relationships": f"{40-rel_loss}/40",
            "cardinalities": f"{10-card_loss}/10",
            "primaryKeys": "20/20",
            "inheritance": "9.5/10"
        }
    else:
        lost = 100 - grade
        rel_loss = int(lost * 0.7)
        card_loss = int(lost * 0.15)
        ent_loss = int(lost * 0.10)
        pk_loss = int(lost * 0.05)
        return {
            "entities": f"{max(0, 20-ent_loss)}/20",
            "relationships": f"{max(0, 40-rel_loss)}/40",
            "cardinalities": f"{max(0, 10-card_loss)}/10",
            "primaryKeys": f"{max(0, 20-pk_loss)}/20",
            "inheritance": "10/10"
        }



if __name__ == "__main__":

    teacher_erd = {"entities": [], "relationships": []}  # Example
    student_erd = {"entities": [], "relationships": []}  # Example

    json_prompt = create_json_prompt(teacher_erd, student_erd)

    print(json.dumps(json_prompt, indent=2))