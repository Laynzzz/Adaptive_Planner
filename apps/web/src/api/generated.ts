// Generated from the FastAPI OpenAPI schema. Run npm run api:generate.
export interface paths {
    "/api/v1/active-plan": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Active Plan */
        get: operations["active_plan_api_v1_active_plan_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/callback": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Callback */
        get: operations["callback_api_v1_auth_callback_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/login": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Login */
        get: operations["login_api_v1_auth_login_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/logout": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Logout */
        post: operations["logout_api_v1_auth_logout_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/availability": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Availability */
        get: operations["get_availability_api_v1_availability_get"];
        /** Set Availability */
        put: operations["set_availability_api_v1_availability_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/blocks/{block_id}/lock": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Lock */
        post: operations["lock_api_v1_blocks__block_id__lock_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/blocks/{block_id}/move": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Move */
        post: operations["move_api_v1_blocks__block_id__move_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/calendar/callback": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Calendar Callback */
        get: operations["calendar_callback_api_v1_calendar_callback_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/calendar/conflicts/{conflict_id}/resolve": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Resolve Calendar Conflict */
        post: operations["resolve_calendar_conflict_api_v1_calendar_conflicts__conflict_id__resolve_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/calendar/connect": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Connect Calendar */
        post: operations["connect_calendar_api_v1_calendar_connect_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/calendar/disconnect": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Disconnect Calendar */
        post: operations["disconnect_calendar_api_v1_calendar_disconnect_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/calendar/publish": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Publish Calendar */
        post: operations["publish_calendar_api_v1_calendar_publish_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/calendar/status": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Calendar Status */
        get: operations["calendar_status_api_v1_calendar_status_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/calendar/sync": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Sync Calendar */
        post: operations["sync_calendar_api_v1_calendar_sync_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/exports/calendar.ics": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Calendar Export */
        get: operations["calendar_export_api_v1_exports_calendar_ics_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/fixed-events": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Events */
        get: operations["list_events_api_v1_fixed_events_get"];
        put?: never;
        /** Create Event */
        post: operations["create_event_api_v1_fixed_events_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/fixed-events/{event_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Patch Event */
        patch: operations["patch_event_api_v1_fixed_events__event_id__patch"];
        trace?: never;
    };
    "/api/v1/interpretations": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Enqueue */
        post: operations["enqueue_api_v1_interpretations_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/interpretations/{interpretation_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Interpretation */
        get: operations["get_interpretation_api_v1_interpretations__interpretation_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/interpretations/{interpretation_id}/accept": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Accept */
        post: operations["accept_api_v1_interpretations__interpretation_id__accept_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/jobs/{job_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Job */
        get: operations["get_job_api_v1_jobs__job_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/me": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Me */
        get: operations["me_api_v1_me_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/proposals": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Proposals */
        get: operations["list_proposals_api_v1_proposals_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/proposals/{proposal_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Proposal */
        get: operations["get_proposal_api_v1_proposals__proposal_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/proposals/{proposal_id}/activate": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Activate */
        post: operations["activate_api_v1_proposals__proposal_id__activate_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/proposals/{proposal_id}/diff": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Proposal Diff */
        get: operations["proposal_diff_api_v1_proposals__proposal_id__diff_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/protected-work": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Protected List */
        get: operations["protected_list_api_v1_protected_work_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/replans": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Generate */
        post: operations["generate_api_v1_replans_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/tasks": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Tasks */
        get: operations["list_tasks_api_v1_tasks_get"];
        put?: never;
        /** Create Task */
        post: operations["create_task_api_v1_tasks_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/tasks/{task_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Task */
        get: operations["get_task_api_v1_tasks__task_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Patch Task */
        patch: operations["patch_task_api_v1_tasks__task_id__patch"];
        trace?: never;
    };
    "/api/v1/tasks/{task_id}/cancel": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Cancel Task */
        post: operations["cancel_task_api_v1_tasks__task_id__cancel_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/tasks/{task_id}/dependencies": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Add Dependency */
        post: operations["add_dependency_api_v1_tasks__task_id__dependencies_post"];
        /** Remove Dependency */
        delete: operations["remove_dependency_api_v1_tasks__task_id__dependencies_delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/tasks/{task_id}/work-logs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** History */
        get: operations["history_api_v1_tasks__task_id__work_logs_get"];
        put?: never;
        /** Observe */
        post: operations["observe_api_v1_tasks__task_id__work_logs_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/weekday-rules": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Rules */
        get: operations["list_rules_api_v1_weekday_rules_get"];
        put?: never;
        /** Create Rule */
        post: operations["create_rule_api_v1_weekday_rules_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/weekday-rules/{rule_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /** Delete Rule */
        delete: operations["delete_rule_api_v1_weekday_rules__rule_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/what-ifs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Preview */
        post: operations["preview_api_v1_what_ifs_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/what-ifs/{preview_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Preview */
        get: operations["get_preview_api_v1_what_ifs__preview_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/what-ifs/{preview_id}/apply": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Apply Preview */
        post: operations["apply_preview_api_v1_what_ifs__preview_id__apply_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/work-logs/{log_id}/corrections": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Correct */
        post: operations["correct_api_v1_work_logs__log_id__corrections_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/health/live": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Live */
        get: operations["live_health_live_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/health/ready": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Ready */
        get: operations["ready_health_ready_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /** AcceptCommand */
        AcceptCommand: {
            /**
             * Confirmed Fields
             * @default []
             */
            confirmed_fields: string[];
            /** Expected Revision */
            expected_revision: number;
            /**
             * Overrides
             * @default {}
             */
            overrides: {
                [key: string]: unknown;
            };
            /** Selected Constraint Keys */
            selected_constraint_keys?: string[] | null;
            /**
             * Selected Task Keys
             * @default []
             */
            selected_task_keys: string[];
        };
        /** AcceptedView */
        AcceptedView: {
            /**
             * Interpretation Id
             * Format: uuid
             */
            interpretation_id: string;
            /** Revision */
            revision: number;
            /** Task Ids */
            task_ids: string[];
            /**
             * Weekday Rule Ids
             * @default []
             */
            weekday_rule_ids: string[];
        };
        /** ActivationView */
        ActivationView: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Planning Revision */
            planning_revision: number;
            /** Publication State */
            publication_state: string;
            /** State */
            state: string;
        };
        /** AppliedView */
        AppliedView: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Revision */
            revision: number;
            /** State */
            state: string;
        };
        /** AvailabilityCommand */
        AvailabilityCommand: {
            /** Expected Revision */
            expected_revision: number;
            /** Windows */
            windows: components["schemas"]["Interval"][];
        };
        /** AvailabilityResponse */
        AvailabilityResponse: {
            /** Revision */
            revision: number;
            /** Timezone */
            timezone: string;
            /** Windows */
            windows: components["schemas"]["Interval"][];
        };
        /** Block */
        Block: {
            /**
             * End
             * Format: date-time
             */
            end: string;
            /** End Slot */
            end_slot: number;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Locked
             * @default false
             */
            locked: boolean;
            /** Original Start */
            original_start?: string | null;
            /**
             * Owner Id
             * Format: uuid
             */
            owner_id: string;
            /**
             * Source
             * @default GREEDY
             */
            source: string;
            /**
             * Start
             * Format: date-time
             */
            start: string;
            /** Start Slot */
            start_slot: number;
            /**
             * Task Id
             * Format: uuid
             */
            task_id: string;
        };
        /** BlockMove */
        BlockMove: {
            new: components["schemas"]["Block"];
            old: components["schemas"]["Block"];
            /**
             * Reason Codes
             * @default []
             */
            reason_codes: string[];
        };
        /** CalendarCommandView */
        CalendarCommandView: {
            /** Authorization Url */
            authorization_url?: string | null;
            /** Revision */
            revision: number;
            /** State */
            state: string;
        };
        /** CalendarConflictView */
        CalendarConflictView: {
            /**
             * Block Id
             * Format: uuid
             */
            block_id: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Reason */
            reason: string;
            /** Remote End */
            remote_end?: string | null;
            /** Remote Start */
            remote_start?: string | null;
        };
        /** CalendarStatusView */
        CalendarStatusView: {
            /** Calendar Id */
            calendar_id?: string | null;
            /**
             * Conflicts
             * @default []
             */
            conflicts: components["schemas"]["CalendarConflictView"][];
            /** Error Code */
            error_code?: string | null;
            /** Last Sync At */
            last_sync_at?: string | null;
            /** Live Configured */
            live_configured: boolean;
            /**
             * Mock Available
             * @default true
             */
            mock_available: boolean;
            /**
             * Pending Count
             * @default 0
             */
            pending_count: number;
            /** Provider */
            provider?: string | null;
            /**
             * Publish Pending
             * @default false
             */
            publish_pending: boolean;
            /**
             * Published Count
             * @default 0
             */
            published_count: number;
            /** Revision */
            revision: number;
            /** State */
            state: string;
            /**
             * Sync Pending
             * @default false
             */
            sync_pending: boolean;
        };
        /** Candidate */
        Candidate: {
            /**
             * Blocks
             * @default []
             */
            blocks: components["schemas"]["Block"][];
            /**
             * Constraint Report
             * @default []
             */
            constraint_report: components["schemas"]["Violation"][];
            /** Planning Revision */
            planning_revision: number;
            score?: components["schemas"]["Score"] | null;
            /** Snapshot Hash */
            snapshot_hash: string;
            solver_metadata?: components["schemas"]["SolverMetadata"];
            /** Source Policy */
            source_policy: string;
            /**
             * Status
             * @enum {string}
             */
            status: "OPTIMAL" | "FEASIBLE" | "INFEASIBLE" | "UNKNOWN" | "MODEL_INVALID";
        };
        /** ConnectCalendar */
        ConnectCalendar: {
            /** Calendar Id */
            calendar_id: string;
            /** Dedicated Synthetic Confirmed */
            dedicated_synthetic_confirmed: boolean;
            /** Expected Revision */
            expected_revision: number;
            /**
             * Provider
             * @enum {string}
             */
            provider: "MOCK" | "GOOGLE";
        };
        /** CreatedRule */
        CreatedRule: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Kind
             * @enum {string}
             */
            kind: "SOFT_AVOID" | "HARD_UNAVAILABLE" | "HARD_NO_DEADLINE";
            /** Revision */
            revision: number;
            /** Weekday */
            weekday: number;
        };
        /** Deadline */
        Deadline: {
            /** Fold */
            fold?: (0 | 1) | null;
            /**
             * Kind
             * @enum {string}
             */
            kind: "DATE" | "TIMESTAMP";
            /**
             * Timezone
             * @default UTC
             */
            timezone: string;
            /** Value */
            value: string;
        };
        /** DependencyCommand */
        DependencyCommand: {
            /** Expected Revision */
            expected_revision: number;
            /**
             * Predecessor Id
             * Format: uuid
             */
            predecessor_id: string;
        };
        /** DisconnectCalendar */
        DisconnectCalendar: {
            /** Expected Revision */
            expected_revision: number;
            /** Keep Remote Events */
            keep_remote_events: boolean;
        };
        /** DraftConstraint */
        DraftConstraint: {
            /** Evidence */
            evidence: components["schemas"]["EvidenceSpan"][];
            /** Key */
            key: string;
            /**
             * Kind
             * @enum {string}
             */
            kind: "SOFT_AVOID" | "HARD_UNAVAILABLE" | "HARD_NO_DEADLINE";
            /**
             * Label
             * @enum {string}
             */
            label: "explicit" | "inferred" | "unknown";
            /**
             * Requires Confirmation
             * @default true
             */
            requires_confirmation: boolean;
            /** Weekday */
            weekday: number;
        };
        /** DraftTask */
        DraftTask: {
            deadline: components["schemas"]["Extracted_Deadline_"];
            /** Key */
            key: string;
            /**
             * Predecessor Keys
             * @default []
             */
            predecessor_keys: string[];
            priority: components["schemas"]["Extracted_int_"];
            remaining_minutes: components["schemas"]["Extracted_int_"];
            title: components["schemas"]["Extracted_str_"];
        };
        /** EvidenceSpan */
        EvidenceSpan: {
            /** End */
            end: number;
            /** Start */
            start: number;
            /** Text */
            text: string;
        };
        /** Extracted[Deadline] */
        Extracted_Deadline_: {
            /** Evidence */
            evidence: components["schemas"]["EvidenceSpan"][];
            /**
             * Label
             * @enum {string}
             */
            label: "explicit" | "inferred" | "unknown";
            /** Requires Confirmation */
            requires_confirmation: boolean;
            value: components["schemas"]["Deadline"] | null;
        };
        /** Extracted[int] */
        Extracted_int_: {
            /** Evidence */
            evidence: components["schemas"]["EvidenceSpan"][];
            /**
             * Label
             * @enum {string}
             */
            label: "explicit" | "inferred" | "unknown";
            /** Requires Confirmation */
            requires_confirmation: boolean;
            /** Value */
            value: number | null;
        };
        /** Extracted[str] */
        Extracted_str_: {
            /** Evidence */
            evidence: components["schemas"]["EvidenceSpan"][];
            /**
             * Label
             * @enum {string}
             */
            label: "explicit" | "inferred" | "unknown";
            /** Requires Confirmation */
            requires_confirmation: boolean;
            /** Value */
            value: string | null;
        };
        /** ExtractionDraft */
        ExtractionDraft: {
            /**
             * Abstained
             * @default false
             */
            abstained: boolean;
            /**
             * Constraints
             * @default []
             */
            constraints: components["schemas"]["DraftConstraint"][];
            /**
             * Schema Version
             * @default extraction-v1
             * @constant
             */
            schema_version: "extraction-v1";
            /**
             * Tasks
             * @default []
             */
            tasks: components["schemas"]["DraftTask"][];
            /**
             * Unresolved Fields
             * @default []
             */
            unresolved_fields: string[];
        };
        /** FixedEventCreate */
        FixedEventCreate: {
            /** End */
            end: string | components["schemas"]["LocalTime"];
            /** Expected Revision */
            expected_revision: number;
            /** Start */
            start: string | components["schemas"]["LocalTime"];
            /** Title */
            title: string;
        };
        /** FixedEventPage */
        FixedEventPage: {
            /** Items */
            items: components["schemas"]["FixedEventResponse"][];
            /** Revision */
            revision: number;
        };
        /** FixedEventPatch */
        FixedEventPatch: {
            /** End */
            end?: string | components["schemas"]["LocalTime"] | null;
            /** Expected Revision */
            expected_revision: number;
            /** Start */
            start?: string | components["schemas"]["LocalTime"] | null;
            /** Title */
            title?: string | null;
        };
        /** FixedEventResponse */
        FixedEventResponse: {
            /** End */
            end: string | components["schemas"]["LocalTime"];
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Revision */
            revision: number;
            /** Start */
            start: string | components["schemas"]["LocalTime"];
            /** Title */
            title: string;
        };
        /** GenerateResponse */
        GenerateResponse: {
            /**
             * Job Id
             * Format: uuid
             */
            job_id: string;
            /** Planning Revision */
            planning_revision: number;
            /** State */
            state: string;
        };
        /** HTTPValidationError */
        HTTPValidationError: {
            /** Detail */
            detail?: components["schemas"]["ValidationError"][];
        };
        /** InterpretCommand */
        InterpretCommand: {
            /** Expected Revision */
            expected_revision: number;
            /**
             * Mode
             * @default mock
             * @enum {string}
             */
            mode: "mock" | "openai";
            /** Text */
            text: string;
        };
        /** InterpretationQueued */
        InterpretationQueued: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Planning Revision */
            planning_revision: number;
            /** State */
            state: string;
        };
        /** InterpretationView */
        InterpretationView: {
            /** Error Code */
            error_code?: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Metadata
             * @default {}
             */
            metadata: {
                [key: string]: unknown;
            };
            /** Planning Revision */
            planning_revision: number;
            proposal?: components["schemas"]["ExtractionDraft"] | null;
            /**
             * Reference Now
             * Format: date-time
             */
            reference_now: string;
            /** Source Text */
            source_text: string;
            /**
             * State
             * @enum {string}
             */
            state: "QUEUED" | "RUNNING" | "READY" | "FAILED" | "ACCEPTED";
            /** Timezone */
            timezone: string;
        };
        /** Interval */
        Interval: {
            /** End */
            end: string | components["schemas"]["LocalTime"];
            /** Start */
            start: string | components["schemas"]["LocalTime"];
        };
        /** JobView */
        JobView: {
            candidate?: components["schemas"]["Candidate"] | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Planning Revision */
            planning_revision: number;
            /** Proposal Id */
            proposal_id?: string | null;
            /** Reason Code */
            reason_code?: string | null;
            /** State */
            state: string;
        };
        /** LocalTime */
        LocalTime: {
            /** Fold */
            fold?: (0 | 1) | null;
            /** Local */
            local: string;
            /**
             * Timezone
             * @default UTC
             */
            timezone: string;
        };
        /** LockCommand */
        LockCommand: {
            /** Expected End */
            expected_end?: string | null;
            /** Expected Revision */
            expected_revision: number;
            /**
             * In Progress
             * @default false
             */
            in_progress: boolean;
            /** Locked */
            locked: boolean;
        };
        /** MeResponse */
        MeResponse: {
            /** Capabilities */
            capabilities: string[];
            /** Csrf Token */
            csrf_token: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name: string;
            /** Revision */
            revision: number;
            /** Timezone */
            timezone: string;
        };
        /** MoveCommand */
        MoveCommand: {
            /**
             * End
             * Format: date-time
             */
            end: string;
            /** Expected Revision */
            expected_revision: number;
            /**
             * Start
             * Format: date-time
             */
            start: string;
        };
        /** PlanDiff */
        PlanDiff: {
            /**
             * Added
             * @default []
             */
            added: components["schemas"]["Block"][];
            /**
             * Moved
             * @default []
             */
            moved: components["schemas"]["BlockMove"][];
            /**
             * Reason Codes
             * @default []
             */
            reason_codes: string[];
            /**
             * Removed
             * @default []
             */
            removed: components["schemas"]["Block"][];
            /**
             * Retained
             * @default []
             */
            retained: components["schemas"]["Block"][];
        };
        /** ProposalList */
        ProposalList: {
            /** Items */
            items: components["schemas"]["ProposalView"][];
        };
        /** ProposalView */
        ProposalView: {
            /** Activated At */
            activated_at?: string | null;
            candidate: components["schemas"]["Candidate"];
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Planning Revision */
            planning_revision: number;
            /** Publication State */
            publication_state: string;
            /** State */
            state: string;
        };
        /** ProtectedItem */
        ProtectedItem: {
            /** Active */
            active: boolean;
            /**
             * End
             * Format: date-time
             */
            end: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Locked */
            locked: boolean;
            /** Source */
            source: string;
            /**
             * Start
             * Format: date-time
             */
            start: string;
            /**
             * Task Id
             * Format: uuid
             */
            task_id: string;
        };
        /** ProtectedList */
        ProtectedList: {
            /** Items */
            items: components["schemas"]["ProtectedItem"][];
            /** Revision */
            revision: number;
        };
        /** ProtectedView */
        ProtectedView: {
            /** End */
            end?: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Locked */
            locked: boolean;
            /** Revision */
            revision: number;
            /** Source */
            source?: string | null;
            /** Start */
            start?: string | null;
        };
        /** ResolveCalendarConflict */
        ResolveCalendarConflict: {
            /**
             * Action
             * @enum {string}
             */
            action: "RESTORE" | "ACCEPT_DELETION" | "REMOVE_COMMITMENT" | "DISCONNECT";
            /** Expected Revision */
            expected_revision: number;
        };
        /** RevisionCommand */
        RevisionCommand: {
            /** Expected Revision */
            expected_revision: number;
        };
        /** RevisionResponse */
        RevisionResponse: {
            /** Revision */
            revision: number;
        };
        /** RuleCommand */
        RuleCommand: {
            /** Expected Revision */
            expected_revision: number;
            /**
             * Kind
             * @enum {string}
             */
            kind: "SOFT_AVOID" | "HARD_UNAVAILABLE" | "HARD_NO_DEADLINE";
            /** Weekday */
            weekday: number;
        };
        /** RuleList */
        RuleList: {
            /** Items */
            items: components["schemas"]["RuleView"][];
            /** Revision */
            revision: number;
            /** Timezone */
            timezone: string;
        };
        /** RuleView */
        RuleView: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Kind
             * @enum {string}
             */
            kind: "SOFT_AVOID" | "HARD_UNAVAILABLE" | "HARD_NO_DEADLINE";
            /** Weekday */
            weekday: number;
        };
        /** Score */
        Score: {
            /**
             * Completion Delay
             * @default 0
             */
            completion_delay: number;
            /**
             * Disruption
             * @default 0
             */
            disruption: number;
            /**
             * Fragmentation
             * @default 0
             */
            fragmentation: number;
            /**
             * Future Work Deficit
             * @default 0
             */
            future_work_deficit: number;
            /**
             * Objective Version
             * @default v1
             */
            objective_version: string;
            /**
             * Preference Mismatch
             * @default 0
             */
            preference_mismatch: number;
            /** Quality */
            readonly quality: number;
            /** Total Penalty */
            readonly total_penalty: number;
        };
        /** SolverMetadata */
        SolverMetadata: {
            /** Budget Ms */
            budget_ms?: number | null;
            /**
             * Constraint Count
             * @default 0
             */
            constraint_count: number;
            /** Reason Code */
            reason_code?: string | null;
            /**
             * Runtime Ms
             * @default 0
             */
            runtime_ms: number;
            /** Seed */
            seed?: number | null;
            /**
             * Variable Count
             * @default 0
             */
            variable_count: number;
        };
        /** TaskChange */
        TaskChange: {
            deadline?: components["schemas"]["Deadline"] | null;
            /** Remaining Minutes */
            remaining_minutes?: number | null;
            /**
             * Task Id
             * Format: uuid
             */
            task_id: string;
        };
        /** TaskCreate */
        TaskCreate: {
            deadline?: components["schemas"]["Deadline"] | null;
            /** Expected Revision */
            expected_revision: number;
            /**
             * Max Block Slots
             * @default 12
             */
            max_block_slots: number;
            /**
             * Min Block Slots
             * @default 2
             */
            min_block_slots: number;
            /**
             * Priority
             * @default 3
             */
            priority: number;
            /** Release At */
            release_at?: string | components["schemas"]["LocalTime"] | null;
            /** Remaining Minutes */
            remaining_minutes: number;
            /**
             * Short Final Allowed
             * @default false
             */
            short_final_allowed: boolean;
            /**
             * Splittable
             * @default true
             */
            splittable: boolean;
            /** Title */
            title: string;
        };
        /** TaskPage */
        TaskPage: {
            /** Items */
            items: components["schemas"]["TaskResponse"][];
            /** Next Cursor */
            next_cursor: string | null;
            /** Revision */
            revision: number;
        };
        /** TaskPatch */
        TaskPatch: {
            deadline?: components["schemas"]["Deadline"] | null;
            /** Expected Revision */
            expected_revision: number;
            /** Max Block Slots */
            max_block_slots?: number | null;
            /** Min Block Slots */
            min_block_slots?: number | null;
            /** Priority */
            priority?: number | null;
            /** Release At */
            release_at?: string | components["schemas"]["LocalTime"] | null;
            /** Remaining Minutes */
            remaining_minutes?: number | null;
            /** Short Final Allowed */
            short_final_allowed?: boolean | null;
            /** Splittable */
            splittable?: boolean | null;
            /** Title */
            title?: string | null;
        };
        /** TaskResponse */
        TaskResponse: {
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            deadline?: components["schemas"]["Deadline"] | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Max Block Slots
             * @default 12
             */
            max_block_slots: number;
            /**
             * Min Block Slots
             * @default 2
             */
            min_block_slots: number;
            /**
             * Owner Id
             * Format: uuid
             */
            owner_id: string;
            /**
             * Predecessor Ids
             * @default []
             */
            predecessor_ids: string[];
            /**
             * Priority
             * @default 3
             */
            priority: number;
            /** Release At */
            release_at?: string | components["schemas"]["LocalTime"] | null;
            /** Remaining Minutes */
            remaining_minutes: number;
            /** Required Slots */
            required_slots: number;
            /** Revision */
            revision: number;
            /**
             * Short Final Allowed
             * @default false
             */
            short_final_allowed: boolean;
            /**
             * Splittable
             * @default true
             */
            splittable: boolean;
            /**
             * State
             * @enum {string}
             */
            state: "TODO" | "IN_PROGRESS" | "DONE" | "CANCELLED";
            /** Title */
            title: string;
        };
        /** ValidationError */
        ValidationError: {
            /** Context */
            ctx?: Record<string, never>;
            /** Input */
            input?: unknown;
            /** Location */
            loc: (string | number)[];
            /** Message */
            msg: string;
            /** Error Type */
            type: string;
        };
        /** Violation */
        Violation: {
            /** Code */
            code: string;
            /** Facts */
            facts?: {
                [key: string]: string | number | boolean | null;
            };
            /**
             * Related Ids
             * @default []
             */
            related_ids: string[];
        };
        /** WhatIfCommand */
        WhatIfCommand: {
            /** Additional Availability */
            additional_availability?: components["schemas"]["Interval"][];
            /** Expected Revision */
            expected_revision: number;
            /** Task Changes */
            task_changes?: components["schemas"]["TaskChange"][];
        };
        /** WhatIfCreated */
        WhatIfCreated: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Job Id
             * Format: uuid
             */
            job_id: string;
            /** State */
            state: string;
        };
        /** WhatIfView */
        WhatIfView: {
            /** Base Revision */
            base_revision: number;
            candidate?: components["schemas"]["Candidate"] | null;
            diff?: components["schemas"]["PlanDiff"] | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Job Id
             * Format: uuid
             */
            job_id: string;
            /** State */
            state: string;
        };
        /** WorkCommand */
        WorkCommand: {
            /** Block Id */
            block_id?: string | null;
            /**
             * Complete
             * @default false
             */
            complete: boolean;
            /** Expected Revision */
            expected_revision: number;
            /** New Remaining Minutes */
            new_remaining_minutes?: number | null;
            /** Observed Minutes */
            observed_minutes: number;
        };
        /** WorkLogList */
        WorkLogList: {
            /** Items */
            items: components["schemas"]["WorkLogView"][];
            /** Revision */
            revision: number;
        };
        /** WorkLogView */
        WorkLogView: {
            /** Block Id */
            block_id?: string | null;
            /** Complete */
            complete: boolean;
            /** Correction Of */
            correction_of?: string | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** New Remaining Minutes */
            new_remaining_minutes: number;
            /** Observed Minutes */
            observed_minutes: number;
            /** Revision */
            revision?: number | null;
            /**
             * Task Id
             * Format: uuid
             */
            task_id: string;
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    active_plan_api_v1_active_plan_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProposalView"] | null;
                };
            };
        };
    };
    callback_api_v1_auth_callback_get: {
        parameters: {
            query?: {
                code?: string;
                state?: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    login_api_v1_auth_login_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    logout_api_v1_auth_logout_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    get_availability_api_v1_availability_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AvailabilityResponse"];
                };
            };
        };
    };
    set_availability_api_v1_availability_put: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AvailabilityCommand"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AvailabilityResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    lock_api_v1_blocks__block_id__lock_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                block_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["LockCommand"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProtectedView"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    move_api_v1_blocks__block_id__move_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                block_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["MoveCommand"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProtectedView"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    calendar_callback_api_v1_calendar_callback_get: {
        parameters: {
            query: {
                state: string;
                code: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    resolve_calendar_conflict_api_v1_calendar_conflicts__conflict_id__resolve_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                conflict_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ResolveCalendarConflict"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CalendarCommandView"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    connect_calendar_api_v1_calendar_connect_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ConnectCalendar"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CalendarCommandView"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    disconnect_calendar_api_v1_calendar_disconnect_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DisconnectCalendar"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CalendarCommandView"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    publish_calendar_api_v1_calendar_publish_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RevisionCommand"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CalendarCommandView"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    calendar_status_api_v1_calendar_status_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CalendarStatusView"];
                };
            };
        };
    };
    sync_calendar_api_v1_calendar_sync_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RevisionCommand"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CalendarCommandView"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    calendar_export_api_v1_exports_calendar_ics_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    list_events_api_v1_fixed_events_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["FixedEventPage"];
                };
            };
        };
    };
    create_event_api_v1_fixed_events_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["FixedEventCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["FixedEventResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    patch_event_api_v1_fixed_events__event_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                event_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["FixedEventPatch"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["FixedEventResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    enqueue_api_v1_interpretations_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["InterpretCommand"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["InterpretationQueued"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_interpretation_api_v1_interpretations__interpretation_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                interpretation_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["InterpretationView"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    accept_api_v1_interpretations__interpretation_id__accept_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                interpretation_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AcceptCommand"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AcceptedView"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_job_api_v1_jobs__job_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                job_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["JobView"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    me_api_v1_me_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MeResponse"];
                };
            };
        };
    };
    list_proposals_api_v1_proposals_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProposalList"];
                };
            };
        };
    };
    get_proposal_api_v1_proposals__proposal_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                proposal_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProposalView"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    activate_api_v1_proposals__proposal_id__activate_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                proposal_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RevisionCommand"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ActivationView"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    proposal_diff_api_v1_proposals__proposal_id__diff_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                proposal_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PlanDiff"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    protected_list_api_v1_protected_work_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProtectedList"];
                };
            };
        };
    };
    generate_api_v1_replans_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RevisionCommand"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["GenerateResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_tasks_api_v1_tasks_get: {
        parameters: {
            query?: {
                state?: string | null;
                cursor?: string | null;
                limit?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TaskPage"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_task_api_v1_tasks_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["TaskCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TaskResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_task_api_v1_tasks__task_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                task_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TaskResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    patch_task_api_v1_tasks__task_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                task_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["TaskPatch"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TaskResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    cancel_task_api_v1_tasks__task_id__cancel_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                task_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RevisionCommand"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TaskResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    add_dependency_api_v1_tasks__task_id__dependencies_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                task_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DependencyCommand"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RevisionResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    remove_dependency_api_v1_tasks__task_id__dependencies_delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                task_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DependencyCommand"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RevisionResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    history_api_v1_tasks__task_id__work_logs_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                task_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["WorkLogList"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    observe_api_v1_tasks__task_id__work_logs_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                task_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["WorkCommand"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["WorkLogView"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_rules_api_v1_weekday_rules_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RuleList"];
                };
            };
        };
    };
    create_rule_api_v1_weekday_rules_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RuleCommand"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CreatedRule"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_rule_api_v1_weekday_rules__rule_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                rule_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RevisionCommand"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RevisionResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    preview_api_v1_what_ifs_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["WhatIfCommand"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["WhatIfCreated"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_preview_api_v1_what_ifs__preview_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                preview_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["WhatIfView"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    apply_preview_api_v1_what_ifs__preview_id__apply_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                preview_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RevisionCommand"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AppliedView"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    correct_api_v1_work_logs__log_id__corrections_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                log_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["WorkCommand"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["WorkLogView"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    live_health_live_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: string;
                    };
                };
            };
        };
    };
    ready_health_ready_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Not ready */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
}
