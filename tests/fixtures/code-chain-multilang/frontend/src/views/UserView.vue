<template><button @click="loadUsers">Load</button></template>
<script>
import { listUsers } from "../api/users";
export default { methods: { async loadUsers() { await listUsers(); } } };
</script>
