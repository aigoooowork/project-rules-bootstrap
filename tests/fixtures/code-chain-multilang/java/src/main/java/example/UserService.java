package example;
class UserService {
    private final UserRepository repository = new UserRepository();
    Object list() { return repository.list(); }
}
