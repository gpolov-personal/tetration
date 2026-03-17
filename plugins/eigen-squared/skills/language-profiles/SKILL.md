---
name: language-profiles
description: "Language-specific toolchain mappings, detection rules, and adaptation notes for the eigen-squared pipeline. Load when any command needs to detect project languages, resolve toolchain commands, or adapt structural patterns for non-Python projects."
---

# Language Profiles — Swarm Engineering Reference

This is the single source of truth for language-specific toolchain mappings and adaptation notes. All eigen-squared commands reference this skill when detecting languages, resolving toolchain commands, or adapting structural patterns.

---

## Language Detection

Detect the project languages by checking for manifest files in `$EIGEN_ROOT`. A project may have **multiple languages** (e.g., Python backend + TypeScript frontend). Check all manifest files — do not stop at the first match:

| Manifest File | Language | Notes |
|--------------|----------|-------|
| `pyproject.toml` / `setup.py` / `setup.cfg` | Python | |
| `package.json` | JavaScript/TypeScript | |
| `go.mod` | Go | |
| `Cargo.toml` | Rust | |
| `*.csproj` / `*.sln` | C#/.NET | |
| `build.gradle` / `build.gradle.kts` | Kotlin/Android OR Java | Check for `com.android.application` or `com.android.library` plugin in build.gradle to identify Android. If present → Kotlin/Android. If absent → plain Java/Kotlin. |
| `pom.xml` | Java | Maven-based Java project |

For multi-language projects, identify the role of each language (e.g., "Python: backend", "TypeScript: frontend"). Use the corresponding language profile for each layer.

---

## Language Profiles

### Python
- test_runner: `python -m pytest`
- test_file_pattern: `test_*.py` or `*_test.py`
- test_dir: `tests/`
- test_marker_system: `@pytest.mark.<tag>`
- test_filter: `-m <tag>`
- coverage: `pytest --cov=<module> --cov-report=term-missing`
- verify_import: `python -c "from <module> import <Name>"`
- interface_mechanism: `typing.Protocol` / `abc.ABC`
- not_implemented: `raise NotImplementedError`
- package_index: `__init__.py`
- doc_comment: Google-style docstring
- env_mock: `@patch.dict(os.environ, {...}, clear=True)`
- expect_exception: `pytest.raises(ExceptionType)`
- e2e_test_dir: `tests/e2e/`
- e2e_marker: `@pytest.mark.e2e`
- e2e_runner: `python -m pytest tests/e2e/ -v`
- e2e_output_format: `--junitxml=e2e-report.xml` (appended to runner)
- e2e_file_pattern: `test_e2e_*.py`

### TypeScript
- test_runner: `npx vitest` / `npx jest`
- test_file_pattern: `*.test.ts` or `*.spec.ts`
- test_dir: `src/` (co-located) or `tests/` or `__tests__/`
- test_marker_system: `describe`/`it` naming or file organization
- test_filter: `--grep <pattern>`
- coverage: `vitest run --coverage`
- verify_import: `tsc --noEmit`
- interface_mechanism: `interface` (compile-time only, no runtime checks)
- not_implemented: `throw new Error('not implemented')`
- package_index: `index.ts` (barrel files, optional)
- doc_comment: JSDoc / TSDoc
- env_mock: manual `process.env` mutation in `beforeEach`/`afterEach`
- expect_exception: `expect(() => ...).toThrow(ErrorType)`
- e2e_test_dir: `tests/e2e/`
- e2e_marker: File naming: `*.e2e.test.ts`
- e2e_runner: Detect: if `playwright.config.ts` exists → `npx playwright test`; else `npx vitest run tests/e2e/` or `npx jest --testPathPattern=e2e`
- e2e_output_format: `--reporter=json` (Playwright) or terminal (vitest/jest)
- e2e_file_pattern: `*.e2e.test.ts` or `*.e2e.spec.ts`

### Go
- test_runner: `go test ./...`
- test_file_pattern: `*_test.go`
- test_dir: co-located with source (same package directory)
- test_marker_system: naming convention (`TestTDDValidation_*`) or build tags
- test_filter: `-run <regex>`
- coverage: `go test -coverprofile=coverage.out ./...`
- verify_import: `go build ./...` (verifies entire package; no single-import check)
- interface_mechanism: `interface` (implicit satisfaction — consumers define interfaces)
- not_implemented: `panic("not implemented")`
- package_index: _(none — packages are directory-based)_
- doc_comment: GoDoc (comment above declaration)
- env_mock: `t.Setenv("key", "value")` (Go 1.17+, auto-restores)
- expect_exception: `require.Panics(t, func() { ... })` (testify) or manual `recover()`
- e2e_test_dir: `e2e/` (top-level package, NOT `tests/e2e/` — Go convention)
- e2e_marker: Build tag: `//go:build e2e`
- e2e_runner: `go test -tags=e2e -json ./e2e/...`
- e2e_output_format: `-json` flag (JSON line output)
- e2e_file_pattern: `*_test.go` (with `//go:build e2e` tag)

### Rust
- test_runner: `cargo test`
- test_file_pattern: inline `#[cfg(test)]` modules or `tests/*.rs`
- test_dir: co-located (unit) or `tests/` (integration)
- test_marker_system: `#[ignore]` + name patterns (no categories)
- test_filter: `cargo test <name_pattern>`
- coverage: `cargo tarpaulin`
- verify_import: `cargo check`
- interface_mechanism: `trait` (explicit `impl Trait for Type` required)
- not_implemented: `unimplemented!()` or `todo!()`
- package_index: `mod.rs` / `lib.rs`
- doc_comment: `///` doc comments (rustdoc)
- env_mock: `temp_env` crate or manual `std::env::set_var`
- expect_exception: `#[should_panic]` attribute or manual catch
- e2e_test_dir: `tests/e2e/` (multi-file integration test with `tests/e2e/main.rs` entry point)
- e2e_marker: Module: `mod e2e_tests`
- e2e_runner: `cargo test --test e2e` (matches binary name "e2e" from `tests/e2e/main.rs`)
- e2e_output_format: Terminal output (stable Rust has no JSON test output)
- e2e_file_pattern: `tests/e2e/main.rs` as entry point, sub-modules via `mod` declarations

### .NET (C#)
- test_runner: `dotnet test`
- test_file_pattern: `*Tests.cs` or `*Test.cs`
- test_dir: separate project (`MyProject.Tests/`)
- test_marker_system: `[Trait("Category", "<tag>")]` (xUnit), `[Category("<tag>")]` (NUnit)
- test_filter: `--filter "Category=<tag>"`
- coverage: `dotnet test --collect:"XPlat Code Coverage"`
- verify_import: `dotnet build`
- interface_mechanism: `interface`
- not_implemented: `throw new NotImplementedException()`
- package_index: _(namespace-based, not file-based)_
- doc_comment: XML doc comments (`/// <summary>`)
- env_mock: `Environment.SetEnvironmentVariable` with cleanup in `Dispose`
- expect_exception: `Assert.Throws<NotImplementedException>(() => ...)`
- e2e_test_dir: `<ProjectName>.Tests.E2E/` (separate `.csproj` project)
- e2e_marker: `[Trait("Category", "E2E")]` (xUnit) or `[Category("E2E")]` (NUnit)
- e2e_runner: `dotnet test <ProjectName>.Tests.E2E/ --filter Category=E2E`
- e2e_output_format: `--logger "junit;LogFileName=e2e-report.xml"`
- e2e_file_pattern: `*E2ETests.cs`

### Kotlin/Android
- test_runner: `./gradlew testDebugUnitTest` (unit tests, JVM-based, no device needed)
- instrumented_test_runner: `./gradlew connectedDebugAndroidTest` (runs on emulator/device)
- test_file_pattern: `*Test.kt` or `*Test.java`
- test_dir: `src/test/java/` (unit, per module) — co-located within each Gradle module
- instrumented_test_dir: `src/androidTest/java/` (instrumented, per module) — runs on device/emulator
- test_marker_system: JUnit 4 `@Category(UnitTest::class)` or test class naming conventions
- test_filter: `--tests "com.example.MyTest"` or `--tests "*Pattern*"`
- coverage: `./gradlew jacocoTestReport` (JaCoCo)
- verify_import: `./gradlew compileDebugKotlin` (compiles all Kotlin sources in debug variant)
- module_build: `./gradlew :module-name:compileDebugKotlin` (compile a specific module only — faster)
- interface_mechanism: `interface` (Kotlin interfaces, explicit `class Foo : MyInterface` implementation)
- not_implemented: `TODO("Not yet implemented")` (throws `NotImplementedError` at runtime)
- package_index: _(none — Kotlin uses package declarations in each file, no barrel/index files)_
- doc_comment: KDoc (`/** ... */`)
- env_mock: varies — `System.setProperty` with cleanup, or test-specific DI configuration
- expect_exception: `assertThrows<ExceptionType> { ... }` (JUnit 5) or `@Test(expected = ExceptionType::class)` (JUnit 4)
- e2e_test_dir: `src/androidTest/java/` (instrumented tests on emulator/device, per module)
- e2e_marker: `@LargeTest` annotation or `@Category(E2ETest::class)`
- e2e_runner: `./gradlew connectedDebugAndroidTest` (requires a running emulator or connected device)
- e2e_output_format: JUnit XML at `build/outputs/androidTest-results/connected/`
- e2e_file_pattern: `*E2ETest.kt` or `*InstrumentedTest.kt`
- build_variants: Android projects have build variants (debug, release, ci, etc.). Use `debug` for development and testing.

---

## System Prerequisites

Each language requires system-level tools that cannot be installed by the swarm (they often need `sudo` or manual setup). Bootstrap checks these before proceeding.

### Python
- **python3** (>= 3.10)
  - check: `python3 --version`
  - install (Ubuntu/Debian): `sudo apt install python3 python3-venv python3-pip`
  - install (macOS): `brew install python@3.12`
- **pip / uv** (package manager)
  - check: `pip --version` or `uv --version`
  - install: `curl -LsSf https://astral.sh/uv/install.sh | sh` (for uv)

### JavaScript/TypeScript
- **node** (>= 18)
  - check: `node --version`
  - install: `curl -fsSL https://fnm.vercel.app/install | bash && fnm install 20`
- **npm / pnpm** (package manager)
  - check: `npm --version` or `pnpm --version`
  - install: `npm install -g pnpm` (for pnpm)

### Go
- **go** (>= 1.21)
  - check: `go version`
  - install: `sudo apt install golang-go` or download from https://go.dev/dl/

### Rust
- **rustc + cargo** (stable)
  - check: `rustc --version && cargo --version`
  - install: `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh`

### .NET (C#)
- **dotnet** (>= 8.0)
  - check: `dotnet --version`
  - install: `sudo apt install dotnet-sdk-8.0` or download from https://dot.net/

### Kotlin / Android
- **java** (JDK >= 17)
  - check: `javac --version`
  - install: `sudo apt install openjdk-17-jdk` or `sdk install java 17.0.x-tem`
- **kotlin** (compiler)
  - check: `kotlinc -version`
  - install: `sdk install kotlin` or via Gradle wrapper (no global install needed if using `./gradlew`)
- **gradle** (build system)
  - check: `gradle --version` or `./gradlew --version`
  - install: Usually bundled via Gradle wrapper (`gradlew`). If missing: `sdk install gradle`
- **android-sdk** (for Android projects only)
  - check: `sdkmanager --version`
  - install: `sudo apt install android-sdk` or download Android Studio command line tools
- **android-emulator** (for E2E testing on Android)
  - check: `emulator -list-avds`
  - install: `sdkmanager "emulator" "system-images;android-34;google_apis;x86_64"` then `avdmanager create avd -n test_device -k "system-images;android-34;google_apis;x86_64"`

### Swift / iOS
- **swift** (compiler)
  - check: `swift --version`
  - install (macOS): Included with Xcode. `xcode-select --install`
  - install (Linux): download from https://swift.org/download/
- **xcodebuild** (for iOS projects, macOS only)
  - check: `xcodebuild -version`
  - install: `xcode-select --install` or install Xcode from App Store
- **ios-simulator** (for E2E testing on iOS, macOS only)
  - check: `xcrun simctl list devices`
  - install: Install via Xcode → Preferences → Platforms

### Flutter
- **flutter** (SDK)
  - check: `flutter --version`
  - install: `git clone https://github.com/flutter/flutter.git && export PATH="$PATH:$(pwd)/flutter/bin"`
- **dart** (included with Flutter)
  - check: `dart --version`

### React Native (mobile)
- Requires **node** (see JavaScript/TypeScript above) plus:
- **watchman** (file watcher)
  - check: `watchman --version`
  - install (macOS): `brew install watchman`
- For Android: requires **java**, **android-sdk**, **android-emulator** (see Kotlin/Android above)
- For iOS: requires **xcodebuild**, **ios-simulator** (see Swift/iOS above, macOS only)
- **cocoapods** (for iOS dependencies)
  - check: `pod --version`
  - install: `sudo gem install cocoapods`

---

## Language Adaptation Notes

These concepts require structural changes, not just syntax swaps.

### File Ownership Model

The swarm uses `files_owned[]` and `test_files_owned[]` to enforce isolation.
This maps 1:1 in Python (one module = one file) but needs adaptation elsewhere:

- **Go**: Ownership operates at the PACKAGE (directory) level. Assign entire package
  directories to one task. Two agents must NOT work on different files in the same
  Go package — this causes symbol conflicts.
- **Rust**: Unit tests are co-located inside source files (`#[cfg(test)]`).
  `test_files_owned` and `files_owned` may overlap. Integration tests in `tests/`
  are separate files and follow normal ownership rules.
- **.NET**: Ownership operates at the project (`.csproj`) level for compilation,
  but file-level ownership is still valid for preventing concurrent edits.
- **Java/Kotlin**: One public class per file. If a stub needs multiple interfaces,
  use multiple stub files (one per interface).
- **Kotlin/Android**: Ownership operates at the **Gradle module** level. Each module
  (`:app`, `:base`, `:feature-wham-tunnel`, etc.) is a compilation unit. Two agents
  should NOT work on different files in the same module unless their files are strictly
  disjoint. Shared module code (like `:base` or common libraries) should go to
  `shared_files`. Use module-specific builds (`./gradlew :module:compileDebugKotlin`)
  for faster verification.

### Import / Dependency Rules

The rule "import from the defining file, not through re-exports" has different
applicability per language:

- **Python**: Import from `src.auth.models`, NOT from `src.auth` (avoids `__init__.py`
  as shared file).
- **TypeScript**: Import from `./auth/models`, NOT from `./auth` (avoids `index.ts`
  barrel files as shared files).
- **Go**: NOT APPLICABLE. Go always imports at the package level. There are no
  barrel/re-export files. The swarm must ensure two agents do not share a package.
- **Rust**: Standard `use crate::auth::models::UserModel;` is idiomatic. Re-exports
  via `mod.rs` are common and acceptable.
- **.NET**: NOT APPLICABLE. `using` statements reference namespaces, which are
  orthogonal to files. No barrel/re-export concern.
- **Kotlin/Android**: NOT APPLICABLE. Kotlin imports are package-level
  (`import com.voxsmart.base.utils.DateUtils`). No barrel/re-export files. However,
  inter-module dependencies must be declared in `build.gradle`
  (`implementation project(':base')`). The swarm must NOT add new module dependencies —
  those go to `shared_files` (the module's `build.gradle`).

### Stub/Interface Lifecycle

The "write stub -> verify import -> overwrite with real implementation" pattern
varies significantly:

- **Python**: Write `Protocol`/`ABC` with `...` bodies -> verify with `python -c` ->
  overwrite file entirely with real implementation. Works as-is.
- **TypeScript**: Write `interface` -> verify with `tsc --noEmit` -> overwrite.
  Note: interfaces are compile-time only, no `isinstance()` runtime checks.
- **Go**: DIFFERENT APPROACH. Consumers define their own interfaces (implicit
  satisfaction). The provider does NOT need to generate a stub file. Instead, the
  plan should define the contract in the manifest, and consumers create their own
  interface types matching that contract. Skip stub generation entirely for Go.
- **Rust**: Write `trait` -> verify with `cargo check` -> DO NOT overwrite. The trait
  definition PERSISTS. Add `impl Trait for ConcreteType` in the same or a new file.
  The instruction "OVERWRITE the stub file entirely" must be changed to "ADD the
  implementation alongside the trait definition."
- **.NET**: Write `interface` -> verify with `dotnet build` -> implement in separate
  class file. The interface file is never overwritten.
- **Kotlin/Android**: Write `interface` -> verify with `./gradlew compileDebugKotlin`
  (or `:module:compileDebugKotlin` for a specific module) -> implement in separate
  class file. The interface file persists. Use `TODO("Not yet implemented")` in
  method bodies for stubs that need concrete classes.

### Stub Detection (Phase 4.1.5)

Checking if a file "still looks like a stub" differs per language:

- **Python**: `grep -rn "raise NotImplementedError" <file>` or check for `...` bodies
- **TypeScript**: Check if file only contains `interface` declarations with no class
- **Go**: N/A (no stub files generated)
- **Rust**: Check if file only contains `trait` with no `impl` blocks
- **.NET**: Check if file only contains `interface` with no class implementations
- **Kotlin/Android**: Check for `TODO("Not yet implemented")` in method bodies,
  or check if file only contains `interface` declarations with no implementing classes

### Test Categorization

Tagging tests as `tdd_validation`, `tdd_contract`, `tdd_unit`:

- **Python**: `@pytest.mark.<tag>` decorators. Filter with `-m <tag>`.
- **TypeScript**: Use test file organization (`validation/*.test.ts`) or describe
  block naming. Filter with `--grep` or file path patterns.
- **Go**: Use naming conventions: `TestTDDValidation_LoginSucceeds`. Filter with
  `-run TestTDDValidation_`. Build tags (`//go:build tdd`) are an alternative but
  exclude tests from normal compilation — use only if intentional.
- **Rust**: Use naming conventions: `mod tdd_validation { #[test] fn login_succeeds() }`.
  Filter with `cargo test tdd_validation`. No first-class tagging mechanism.
- **.NET**: Use xUnit `[Trait("Category", "tdd_validation")]`, NUnit
  `[Category("tdd_validation")]`, or MSTest `[TestCategory("tdd_validation")]`.
  Filter with `--filter "Category=tdd_validation"`.
- **Kotlin/Android**: Use JUnit 4 `@Category(TddValidation::class)` or naming
  conventions (`TddValidation_LoginSucceeds`). Filter with `--tests "*TddValidation*"`.
  For JUnit 5 (if adopted): `@Tag("tdd_validation")`.

Tagging E2E tests as `e2e` (written by the `e2e-tester` teammate, NOT by workers):

- **Python**: `@pytest.mark.e2e` decorator. Filter with `-m e2e`.
- **TypeScript**: File naming: `*.e2e.test.ts` or `*.e2e.spec.ts`.
  Filter with file path pattern or `--grep e2e`.
- **Go**: Build tag: `//go:build e2e`. Filter with `-tags=e2e`.
  Excluded from normal `go test ./...` runs (intentional).
- **Rust**: Test target naming: binary `e2e` from `tests/e2e/main.rs`.
  Filter with `cargo test --test e2e`.
- **.NET**: `[Trait("Category", "E2E")]` (xUnit) or `[Category("E2E")]` (NUnit).
  Filter with `--filter Category=E2E`.
- **Kotlin/Android**: E2E tests are instrumented tests in `src/androidTest/`.
  Use `@LargeTest` annotation or `@Category(E2ETest::class)`.
  Run with `./gradlew connectedDebugAndroidTest`. Requires a running emulator.

### Package Index / Shared Files

`__init__.py` serves as both module initializer and re-export aggregator in Python.
Other languages handle these roles differently:

- **Python**: `__init__.py` — shared file that needs integration.
- **TypeScript**: `index.ts` barrel files — shared file that needs integration.
- **Go**: No equivalent. Packages export all capitalized symbols automatically.
  The integration task does NOT need to update any "package index" file for Go.
- **Rust**: `mod.rs` or `lib.rs` declares the module tree. Shared file if multiple
  tasks add modules to the same crate.
- **.NET**: No equivalent. Namespaces are declared inline in each file.
  The integration task does NOT need to update any "package index" file for .NET.
- **Kotlin/Android**: No package index files. However, the module's `build.gradle`
  declares inter-module dependencies (`implementation project(':base')`). If a task
  adds a new module dependency, the `build.gradle` is a shared file. Also,
  `settings.gradle` declares which modules exist — adding a new module requires
  updating `settings.gradle` (shared file).

### E2E Testing Lifecycle

E2E tests are structurally different from validation/unit tests in the swarm:

- **Ownership**: E2E tests are owned exclusively by the `e2e-tester` teammate.
  No worker owns E2E test files. The `e2e_test_dir` MUST NOT overlap with
  any task's `test_files_owned`.
- **Timing**: E2E tests run AFTER all workers complete and integration finishes.
  They validate the assembled system, not individual components.
- **Authorship**: The E2E teammate both writes and runs E2E tests (unlike
  workers, who write validation tests then implement code to pass them).
- **Marker**: Use `e2e` (NOT `tdd_e2e`). E2E tests are post-integration
  validation, not part of the TDD cycle.

Language-specific E2E lifecycle considerations:

- **Python**: If the project uses `behave` for acceptance tests (check for
  `tests/acceptance/features/`), the E2E teammate should evaluate whether
  existing BDD scenarios already cover the planned E2E flows before writing
  new pytest-based E2E tests. For API testing, use the application's test
  client (e.g., `httpx.AsyncClient` for FastAPI, `TestClient` for Django).
- **TypeScript**: Detect the E2E framework from project configuration:
  - `playwright.config.ts` exists → use Playwright (browser-based E2E)
  - No UI/browser component → use the project's test runner (vitest/jest)
  - If ambiguous → create a `[QUESTION]` task for the leader
- **Go**: E2E tests live in a dedicated top-level package (`e2e/`) using build
  tags (`//go:build e2e`). This is an intentional exception to Go's co-location
  model. Use `httptest.Server` for API E2E tests. The E2E package should import
  the application's main setup function.
- **Rust**: E2E tests in `tests/e2e/` are compiled as a separate test binary
  via `tests/e2e/main.rs`. For server-based E2E, use `tokio::test` with an
  embedded test server (e.g., `actix_test` for Actix, `axum::Server` bound
  to `127.0.0.1:0` for Axum).
- **.NET**: E2E tests require a separate `.csproj` project
  (`<ProjectName>.Tests.E2E/`). Use `WebApplicationFactory<T>` for API E2E
  tests (ASP.NET Core). The integration phase should add the project to the
  solution file if it does not exist.
- **Kotlin/Android**: E2E tests are instrumented tests in `src/androidTest/java/`
  that run on a real emulator or device. Use Espresso for UI testing, or
  UI Automator for cross-app flows. For API-only E2E (testing backend
  communication without UI), use OkHttp/Retrofit test clients in instrumented
  tests. The emulator must be running before tests start — this is part of the
  E2E Testing epic's infrastructure setup.

### E2E Framework Detection

When the E2E teammate starts, it must determine the correct E2E framework.
Detection uses manifest files and configuration:

- **Python**: Check for `behave` in pyproject.toml dependencies, or
  `tests/acceptance/` directory. If present, BDD is available. Otherwise
  default to pytest.
- **TypeScript**: Check for `playwright.config.ts` or `@playwright/test`
  in package.json dependencies. If present, use Playwright. Otherwise use
  the project's unit test runner (vitest or jest).
- **Go**: No framework detection needed — `go test` with build tags is
  the standard approach.
- **Rust**: No framework detection needed — `cargo test` with test target
  filtering is the standard approach.
- **.NET**: Check for `Microsoft.AspNetCore.Mvc.Testing` in the .csproj.
  If present, use `WebApplicationFactory`. Otherwise default to `dotnet test`
  with HTTP client tests.
- **Kotlin/Android**: Check for Espresso dependencies (`androidx.test.espresso`)
  in `build.gradle`. If present → use Espresso for UI E2E. Check for Compose
  testing (`androidx.compose.ui:ui-test-junit4`) for Compose-based UI. For
  cross-app or system-level tests, check for UI Automator
  (`androidx.test.uiautomator`). Default: Espresso for UI, instrumented JUnit
  for non-UI.

### E2E Test Type Tooling

When the e2e-tester encounters a scenario with a specific `test_type`, it should
use the appropriate tooling. **All test types require real running services** started
by `e2e_setup_command` — no in-process mocks of internal services.

**test_type: `api`**
- Python: `httpx` or `requests` against `http://localhost:<port>` — do NOT use FastAPI's `TestClient`
- TypeScript: `fetch` or `axios` against running server — do NOT use supertest with in-process app
- Go: `net/http` client against `http://localhost:<port>` — do NOT use `httptest.Server` with in-process handler
- Rust: `reqwest` against running server — do NOT use embedded test server
- .NET: `HttpClient` against running server — do NOT use `WebApplicationFactory` (use real deployed server)
- Kotlin/Android: `OkHttp` or `Retrofit` client against running server in instrumented test

**test_type: `browser`**
- All languages: Use Playwright if `playwright.config.ts` or `@playwright/test` detected
- Fallback: Use `agent-browser` skill (Vercel's agent-browser CLI)
- The frontend dev server MUST be running (part of the E2E Testing epic's infrastructure)
- Tests navigate real pages, fill forms, click buttons, verify content

**test_type: `mobile`**
- Kotlin/Android: Espresso for in-app UI testing, UI Automator for cross-app flows.
  Requires a running Android emulator. Use `ActivityScenario` to launch activities.
  For Compose UI: use `createComposeRule()` with `onNodeWithText()` / `onNodeWithTag()`.
- Swift/iOS: XCUITest for UI testing. Requires iOS Simulator.
- React Native: Detox or Maestro for cross-platform E2E.
- Flutter: `flutter_test` + `integration_test` package.

**test_type: `pipeline`**
- Inject test data into the source (S3/MinIO upload, queue message publish, file drop)
- Poll the target store with timeout (database query, API call, file check)
- Recommended polling: check every 2 seconds, timeout at 60 seconds
- Verify data transformation correctness in the output store

**test_type: `full_stack`**
- Combine `pipeline` + `browser` + `api` tooling as needed
- Typical flow: inject data → wait for processing → verify via API → verify in browser
- Use the longest timeout of all involved types

**Infrastructure detection for `e2e_setup_command` generation:**
- If `docker-compose.test.yml` exists → `docker-compose -f docker-compose.test.yml up -d --wait`
- Else if `docker-compose.yml` exists → `docker-compose up -d --wait`
- If `playwright.config.ts` exists → add `npx playwright install` to setup
- If `package.json` has `dev` script and browser tests needed → add `npm run dev &` to setup

---

## Stack-Specific Skills

Skills organized by tech stack. The orchestrator uses this table instead of scanning all skills at runtime. When new skills are added to the plugin, add them here.

### By Language

| Language | Testing Skills | Best Practices Skills |
|----------|---------------|----------------------|
| Python | `python-testing-patterns` | `python-expert` |
| TypeScript + React/Next.js | — | `react-best-practices`, `composition-patterns` |
| TypeScript + React Native | — | `react-native-skills` |
| TypeScript (no framework) | — | — |
| C# / .NET | `csharp-pro` | `dotnet-backend-patterns` |
| Kotlin/Android | — | — |

### By Domain (match against plan/issue content, not language)

| Domain Signal (in plan/issue) | Skill |
|-------------------------------|-------|
| AI agent, MCP tool, autonomous, agent loop | `agent-native-architecture` |
| Browser E2E, web UI test, form interaction, navigation test | `agent-browser` |
| Frontend UI, web components, pages, visual design | `frontend-design` |
| UI review, accessibility, UX audit, design compliance | `web-design-guidelines` |
| Security review, vulnerability audit, secure coding, security report | `security-best-practices` |
| System architecture, architecture diagram, tech stack decision, dependency analysis, system design | `senior-architect` |

### Lookup Procedure

1. Match `<detected_language>` (always singular) against the "By Language" table
2. If `<detected_framework>` is known, use the language+framework row (e.g., "TypeScript + React/Next.js")
3. Match plan/issue keywords against the "By Domain" table
4. Return all matched skill names as `<relevant_skills>`
5. For each skill, the path is `skills/<skill_name>/SKILL.md` relative to the plugin root
