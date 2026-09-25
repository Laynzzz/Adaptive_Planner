// Generated from the FastAPI OpenAPI schema. Run npm run api:generate.
export interface paths {
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
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
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
