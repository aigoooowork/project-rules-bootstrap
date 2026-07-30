package example;
class UserController {
    private final UserService service = new UserService();
    Object list() { return service.list(); }
}
