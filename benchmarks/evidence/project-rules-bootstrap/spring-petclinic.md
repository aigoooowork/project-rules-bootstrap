# Spring PetClinic — owner web flow

## Scope
Owner and pet web behavior under `src/main/java/org/springframework/samples/petclinic/owner/`.

## Confirmed facts
- `OwnerController.processFindForm()` in `src/main/java/org/springframework/samples/petclinic/owner/OwnerController.java` normalizes the submitted last name, creates pagination through `findPaginatedForOwnersLastName()`, and calls `OwnerRepository.findByLastNameStartingWith()` in `src/main/java/org/springframework/samples/petclinic/owner/OwnerRepository.java`.
- The controller selects the not-found form, a single-owner redirect, or the paginated owner list from the repository result.
- `OwnerRepository` extends Spring Data `JpaRepository`; persistence query behavior is covered by `ClinicServiceTests`.
- Controller behavior is covered by `OwnerControllerTests`; pet creation additionally crosses `PetController`, `PetValidator`, the `Owner` aggregate, and `PetControllerTests`/`PetValidatorTests`.

## Execution rules
- For owner search changes, trace `processFindForm()` → `findPaginatedForOwnersLastName()` → `findByLastNameStartingWith()` → `addPaginationModel()` (or the redirect/not-found branch), and update `src/test/java/org/springframework/samples/petclinic/owner/OwnerControllerTests.java` plus repository-facing tests when the query contract changes.
- For pet validation changes, follow `PetController.processCreationForm()` through `PetValidator` and the owning `Owner` aggregate; keep controller error rendering and validator unit coverage aligned.
- Keep production changes under `src/main/java` and mirror the affected package in `src/test/java`.

## Verification
- Focused owner web flow: `./mvnw -Dtest=OwnerControllerTests test`
- Focused pet validation: `./mvnw -Dtest=PetControllerTests,PetValidatorTests test`
- Full build and configured quality plugins: `./mvnw verify`

## Related rules
No additional canonical group is needed for this benchmark task.
