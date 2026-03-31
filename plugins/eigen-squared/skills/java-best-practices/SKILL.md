---
name: java-best-practices
description: "Java best practices combining enterprise architecture (Spring Boot 3.x, microservices, reactive programming) with coding standards (naming, immutability, Optional, streams, exceptions, generics, project layout). Use when building, reviewing, or debugging Java applications."
license: MIT
metadata:
  author: merged from https://github.com/Jeffallan and https://github.com/terenceallen
  version: "1.0.0"
  domain: language
  triggers: Spring Boot, Java, microservices, Spring Cloud, JPA, Hibernate, WebFlux, reactive, Java Enterprise, coding standards
  role: architect
  scope: implementation
  output-format: code
  related-skills: kotlin-best-practices
---

# Java Best Practices

Enterprise Java specialist focused on Spring Boot 3.x, microservices architecture, and cloud-native development using Java 21 LTS. Also enforces coding standards for readable, maintainable Java (17+) code.

## When to Activate

- Building, configuring, or debugging enterprise Java applications
- Writing or reviewing Java code in Spring Boot projects
- Implementing WebFlux endpoints, optimizing JPA queries, configuring Spring Security
- Enforcing naming, immutability, or exception handling conventions
- Working with records, sealed classes, or pattern matching (Java 17+)
- Reviewing use of Optional, streams, or generics
- Structuring packages and project layout

## Core Principles

- Prefer clarity over cleverness
- Immutable by default; minimize shared mutable state
- Fail fast with meaningful exceptions
- Consistent naming and package structure
- Externalize all configuration (never hardcode values)

## Core Workflow

1. **Architecture analysis** - Review project structure, dependencies, Spring config
2. **Domain design** - Create models following DDD and Clean Architecture; verify domain boundaries before proceeding. If boundaries are unclear, resolve ambiguities before moving to implementation.
3. **Implementation** - Build services with Spring Boot best practices
4. **Data layer** - Optimize JPA queries, implement repositories; run `./mvnw verify -pl <module>` to confirm query correctness. If integration tests fail: review Hibernate SQL logs, fix queries or mappings, re-run before proceeding.
5. **Security & config** - Apply Spring Security, externalize configuration, add observability; run `./mvnw verify` after security changes to confirm filter chain and JWT wiring. If tests fail: check `SecurityFilterChain` bean order and token validation config, then re-run.
6. **Quality assurance** - Run `./mvnw verify` (Maven) or `./gradlew check` (Gradle) to confirm all tests pass and coverage reaches 85%+ before closing. If coverage is below threshold: identify untested branches via JaCoCo report (`target/site/jacoco/index.html`), add missing test cases, re-run.

## Reference Guide

Load detailed guidance based on context:

| Topic | Reference | Load When |
|-------|-----------|-----------|
| Spring Boot | `references/spring-boot-setup.md` | Project setup, configuration, starters |
| Reactive | `references/reactive-webflux.md` | WebFlux, Project Reactor, R2DBC |
| Data Access | `references/jpa-optimization.md` | JPA, Hibernate, query tuning |
| Security | `references/spring-security.md` | OAuth2, JWT, method security |
| Testing | `references/testing-patterns.md` | JUnit 5, TestContainers, Mockito |

## Coding Standards

### Naming

```java
// Classes/Records: PascalCase
public class MarketService {}
public record Money(BigDecimal amount, Currency currency) {}

// Methods/fields: camelCase
private final MarketRepository marketRepository;
public Market findBySlug(String slug) {}

// Constants: UPPER_SNAKE_CASE
private static final int MAX_PAGE_SIZE = 100;
```

### Immutability

```java
// Favor records and final fields
public record MarketDto(Long id, String name, MarketStatus status) {}

public class Market {
  private final Long id;
  private final String name;
  // getters only, no setters
}
```

### Optional Usage

```java
// Return Optional from find* methods
Optional<Market> market = marketRepository.findBySlug(slug);

// Map/flatMap instead of get()
return market
    .map(MarketResponse::from)
    .orElseThrow(() -> new EntityNotFoundException("Market not found"));
```

### Streams Best Practices

```java
// Use streams for transformations, keep pipelines short
List<String> names = markets.stream()
    .map(Market::name)
    .filter(Objects::nonNull)
    .toList();

// Avoid complex nested streams; prefer loops for clarity
```

### Exceptions

- Use unchecked exceptions for domain errors; wrap technical exceptions with context
- Create domain-specific exceptions (e.g., `MarketNotFoundException`)
- Avoid broad `catch (Exception ex)` unless rethrowing/logging centrally

```java
throw new MarketNotFoundException(slug);
```

### Generics and Type Safety

- Avoid raw types; declare generic parameters
- Prefer bounded generics for reusable utilities

```java
public <T extends Identifiable> Map<Long, T> indexById(Collection<T> items) { ... }
```

### Project Structure (Maven/Gradle)

```
src/main/java/com/example/app/
  config/
  controller/
  service/
  repository/
  domain/
  dto/
  util/
src/main/resources/
  application.yml
src/test/java/... (mirrors main)
```

### Formatting and Style

- Use 2 or 4 spaces consistently (project standard)
- One public top-level type per file
- Keep methods short and focused; extract helpers
- Order members: constants, fields, constructors, public methods, protected, private

### Code Smells to Avoid

- Long parameter lists -> use DTO/builders
- Deep nesting -> early returns
- Magic numbers -> named constants
- Static mutable state -> prefer dependency injection
- Silent catch blocks -> log and act or rethrow

### Logging

```java
private static final Logger log = LoggerFactory.getLogger(MarketService.class);
log.info("fetch_market slug={}", slug);
log.error("failed_fetch_market slug={}", slug, ex);
```

### Null Handling

- Accept `@Nullable` only when unavoidable; otherwise use `@NonNull`
- Use Bean Validation (`@NotNull`, `@NotBlank`) on inputs

## Constraints

### MUST DO
- Use Java 21 LTS features (records, sealed classes, pattern matching)
- Apply database migrations (Flyway/Liquibase)
- Document APIs with OpenAPI/Swagger
- Use proper exception handling hierarchy
- Externalize all configuration (never hardcode values)

### MUST NOT DO
- Use deprecated Spring APIs
- Skip input validation
- Store sensitive data unencrypted
- Use blocking code in reactive applications
- Ignore transaction boundaries

## Code Examples

### Minimal WebFlux REST Endpoint

```java
@RestController
@RequestMapping("/api/v1/orders")
@RequiredArgsConstructor
public class OrderController {

    private final OrderService orderService;

    @GetMapping("/{id}")
    public Mono<ResponseEntity<OrderDto>> getOrder(@PathVariable UUID id) {
        return orderService.findById(id)
                .map(ResponseEntity::ok)
                .defaultIfEmpty(ResponseEntity.notFound().build());
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public Mono<OrderDto> createOrder(@Valid @RequestBody CreateOrderRequest request) {
        return orderService.create(request);
    }
}
```

### JPA Repository with Optimized Query

```java
public interface OrderRepository extends JpaRepository<Order, UUID> {

    // Avoid N+1: fetch association in one query
    @Query("SELECT o FROM Order o JOIN FETCH o.items WHERE o.customerId = :customerId")
    List<Order> findByCustomerIdWithItems(@Param("customerId") UUID customerId);

    // Projection to limit fetched columns
    @Query("SELECT new com.example.dto.OrderSummary(o.id, o.status, o.total) FROM Order o WHERE o.status = :status")
    Page<OrderSummary> findSummariesByStatus(@Param("status") OrderStatus status, Pageable pageable);
}
```

### Spring Security OAuth2 JWT Configuration

```java
@Configuration
@EnableMethodSecurity
public class SecurityConfig {

    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        return http
                .csrf(AbstractHttpConfigurer::disable)
                .sessionManagement(s -> s.sessionCreationPolicy(STATELESS))
                .authorizeHttpRequests(auth -> auth
                        .requestMatchers("/actuator/health").permitAll()
                        .anyRequest().authenticated())
                .oauth2ResourceServer(oauth2 -> oauth2.jwt(Customizer.withDefaults()))
                .build();
    }
}
```

## Testing Expectations

- JUnit 5 + AssertJ for fluent assertions
- Mockito for mocking; avoid partial mocks where possible
- Favor deterministic tests; no hidden sleeps
- TestContainers for integration tests

## Output Templates

When implementing Java features, provide:
1. Domain models (entities, DTOs, records)
2. Service layer (business logic, transactions)
3. Repository interfaces (Spring Data)
4. Controller/REST endpoints
5. Test classes with comprehensive coverage
6. Brief explanation of architectural decisions

## Knowledge Reference

Spring Boot 3.x, Java 21, Spring WebFlux, Project Reactor, Spring Data JPA, Spring Security, OAuth2/JWT, Hibernate, R2DBC, Spring Cloud, Resilience4j, Micrometer, JUnit 5, TestContainers, Mockito, Maven/Gradle, JaCoCo, AssertJ

**Remember**: Keep code intentional, typed, and observable. Optimize for maintainability over micro-optimizations unless proven necessary.
