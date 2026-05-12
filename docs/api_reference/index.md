# API Reference

This section contains the API documentation for Jobify, automatically generated from the source code.

::: jobify
    options:
      show_root_heading: true
      members:
        - INJECT
        - Cron
        - CronContext
        - GracePolicy
        - Job
        - JobContext
        - JobRouter
        - JobStatus
        - Jobify
        - MisfirePolicy
        - OuterContext
        - Plugin
        - RequestState
        - RunMode
        - Runnable
        - ScheduleBuilder
        - SmartRetry
        - State
        - PydanticConverter

::: jobify.serializers
    options:
      show_root_heading: true
      members:
        - Serializer
        - CBORSerializer
        - MsgpackSerializer
        - OrjsonSerializer
        - JSONSerializer
        - ExtendedJSONSerializer
        - UnsafePickleSerializer

::: jobify.typeadapter
    options:
      show_root_heading: true
      members:
        - Dumper
        - Loader
        - PydanticConverter

::: jobify.router
    options:
      show_root_heading: true
      members:
        - Route
        - JobRouter
        - NodeRoute
        - RootRoute

::: jobify.middleware
    options:
      show_root_heading: true
      members:
        - BaseMiddleware
        - BaseOuterMiddleware
        - CallNext
        - CallNextOuter
        - JobifyQueue
        - QueueMiddleware

::: jobify.exceptions
    options:
      show_root_heading: true
      members:
        - ApplicationStateError
        - BaseJobifyError
        - DuplicateJobError
        - JobFailedError
        - JobNotCompletedError
        - JobTimeoutError
        - RouteAlreadyRegisteredError
