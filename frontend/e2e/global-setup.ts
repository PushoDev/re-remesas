import { deleteE2eUsers, seedDemoUsers } from './backend'

export default function globalSetup(): void {
  deleteE2eUsers()
  seedDemoUsers()
}
