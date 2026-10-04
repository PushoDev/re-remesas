import { execFileSync } from 'node:child_process'
import path from 'node:path'

const backendDir = path.resolve(import.meta.dirname, '../../backend')

function manage(...args: string[]): void {
  execFileSync(path.join(backendDir, 'venv/bin/python'), ['manage.py', ...args], { cwd: backendDir, stdio: 'pipe' })
}

/** Restores the four demo users to their known state. */
export function seedDemoUsers(): void {
  manage('seed_demo_users')
}

/** Removes the accounts the e2e tests registered (their emails start with "e2e-"). */
export function deleteE2eUsers(): void {
  manage(
    'shell',
    '-c',
    "from apps.users.models import User; User.objects.filter(email__startswith='e2e-', email__endswith='@rere.test').delete()",
  )
}
