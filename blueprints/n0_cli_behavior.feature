Feature: N0 safe CLI

  Scenario: Preflight never remediates
    Given the N0 phase is authorized
    When I run "npi preflight"
    Then it reports available and unavailable capabilities
    And it does not install, update, pull, or change system settings

  Scenario: Dry-run ingest is non-mutating
    Given an empty SQLite state database
    And the approved three-fixture source
    When I run "npi ingest --input <fixture_dir> --dry-run" twice
    Then both normalized outputs are identical
    And the asset count remains zero
    And all fixture SHA-256, size, and mtime are unchanged

  Scenario: Non-dry-run is locked
    When I run "npi ingest --input <fixture_dir>"
    Then exit code is 8
    And error code is "NPI_GATE_NOT_AUTHORIZED"

  Scenario: Source overlap is refused
    Given runtime is inside source
    When I run dry-run ingest
    Then exit code is 4
    And no source file is touched

  Scenario: Recovery skeleton
    Given a stage run marked RUNNING with an expired lease
    When the database is reopened
    Then the run is reported as interrupted/recoverable
    And no completed output is invented
