import axios from "axios";
export const listUsers = () => axios.get("/api/users");
