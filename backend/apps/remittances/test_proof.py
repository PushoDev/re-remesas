from decimal import Decimal
from pathlib import Path

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.common.overview import remittance_counts
from apps.exchange_rates.models import ExchangeRate
from apps.users.models import User

from .models import Remittance
from .services import create_remittance

pytestmark = pytest.mark.django_db

PNG = b'\x89PNG\r\n\x1a\n' + b'\x00' * 64
JPG = b'\xff\xd8\xff\xe0' + b'\x00' * 64
PDF = b'%PDF-1.4\n' + b'x' * 64


@pytest.fixture(autouse=True)
def isolated_media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    return tmp_path


@pytest.fixture(autouse=True)
def usd_rate():
    return ExchangeRate.objects.create(
        currency='USD', base_rate=Decimal('700'), standard_spread_percent=Decimal('5'), vip_spread_percent=Decimal('2'),
    )


def make_user(email='ana@example.com', **extra):
    return User.objects.create_user(username=email, email=email, password='x', **extra)


def client_for(user=None):
    client = APIClient()
    if user:
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return client


@pytest.fixture
def customer():
    return make_user()


@pytest.fixture
def admin():
    return client_for(make_user('admin@example.com', is_staff=True))


def new_remittance(user, method='ZELLE'):
    remittance, _ = create_remittance(
        user, amount=Decimal('100'), currency='USD', recipient_name='Rosa', recipient_phone='+5351234567',
        delivery_method='CASH_DELIVERY', recipient_address='Calle 1', payment_method=method,
    )
    return remittance


def proof_url(remittance):
    return f'/api/remittances/{remittance.tracking_id}/payment-proof/'


def admin_proof_url(remittance):
    return f'/api/admin/remittances/{remittance.tracking_id}/proof/'


def send(user, remittance, **fields):
    return client_for(user).post(proof_url(remittance), fields, format='multipart')


def upload(content, name='comprobante.png'):
    return SimpleUploadedFile(name, content)


class TestReference:
    def test_a_reference_alone_is_enough(self, customer):
        remittance = new_remittance(customer)

        response = send(customer, remittance, reference='  ZEL-2026   1004  ')

        assert response.status_code == 200
        assert response.data['payment_reference'] == 'ZEL-2026 1004'
        assert response.data['has_proof_file'] is False

    def test_it_leaves_a_trace_in_the_history(self, customer):
        remittance = new_remittance(customer)

        send(customer, remittance, reference='ZEL-1')

        entry = remittance.status_log.last()
        assert (entry.from_status, entry.to_status, entry.source, entry.changed_by) == (
            'PENDING_PAYMENT', 'PENDING_PAYMENT', 'CUSTOMER', customer)
        assert 'comprobante' in entry.note and 'ZEL-1' in entry.note

    def test_the_state_does_not_change(self, customer):
        remittance = new_remittance(customer)

        send(customer, remittance, reference='ZEL-1')

        remittance.refresh_from_db()
        assert remittance.status == 'PENDING_PAYMENT'

    def test_it_marks_the_remittance_as_needing_review(self, customer):
        remittance = new_remittance(customer)
        assert remittance_counts()['needs_review'] == 0

        send(customer, remittance, reference='ZEL-1')

        assert remittance_counts()['needs_review'] == 1

    def test_nothing_at_all_is_rejected(self, customer):
        response = send(customer, new_remittance(customer))

        assert response.status_code == 400
        assert 'referencia' in response.data['non_field_errors'][0]

    def test_a_blank_reference_without_a_file_is_rejected(self, customer):
        assert send(customer, new_remittance(customer), reference='   ').status_code == 400

    def test_a_reference_that_is_too_long_is_rejected(self, customer):
        assert 'reference' in send(customer, new_remittance(customer), reference='x' * 121).data


class TestTheFile:
    @pytest.mark.parametrize('content, name', [(PNG, 'foto.png'), (JPG, 'foto.jpg'), (JPG, 'FOTO.JPEG'), (PDF, 'recibo.pdf')])
    def test_images_and_pdfs_are_accepted(self, customer, content, name):
        remittance = new_remittance(customer)

        response = send(customer, remittance, file=upload(content, name))

        assert response.status_code == 200
        assert response.data['has_proof_file'] is True

    def test_the_file_is_stored_under_a_random_name_in_the_remittances_folder(self, customer, isolated_media):
        remittance = new_remittance(customer)

        send(customer, remittance, file=upload(PNG, 'MiTarjeta-1234.png'))

        remittance.refresh_from_db()
        stored = Path(remittance.payment_proof.name)
        assert stored.parent == Path('payment_proofs') / remittance.tracking_id
        assert stored.suffix == '.png' and 'MiTarjeta' not in stored.name
        assert (isolated_media / stored).read_bytes() == PNG

    @pytest.mark.parametrize('name', ['virus.exe', 'pagina.html', 'imagen.svg', 'script.php', 'archivo', 'doc.docx', 'x.png.exe'])
    def test_other_formats_are_rejected_even_with_innocent_content(self, customer, name):
        response = send(customer, new_remittance(customer), file=upload(PNG, name))

        assert response.status_code == 400
        assert 'Formato no admitido' in response.data['file'][0]

    @pytest.mark.parametrize('content, name', [
        (b'MZ\x90\x00' + b'\x00' * 60, 'foto.png'),            # an executable pretending to be a picture
        (b'<script>alert(1)</script>', 'foto.jpg'),             # HTML pretending to be a picture
        (PNG, 'recibo.pdf'),                                    # a real PNG named .pdf
        (PDF, 'foto.png'),                                      # a real PDF named .png
        (b'GIF89a' + b'\x00' * 20, 'foto.png'),
    ])
    def test_a_file_whose_content_does_not_match_its_type_is_rejected(self, customer, content, name):
        response = send(customer, new_remittance(customer), file=upload(content, name))

        assert response.status_code == 400
        assert 'no coincide' in response.data['file'][0]

    def test_an_empty_file_is_rejected(self, customer):
        response = send(customer, new_remittance(customer), file=upload(b'', 'vacio.png'))

        assert response.status_code == 400 and 'vacío' in response.data['file'][0]

    def test_a_file_over_the_limit_is_rejected(self, customer, settings):
        settings.PAYMENT_PROOF_MAX_BYTES = 100
        remittance = new_remittance(customer)

        response = send(customer, remittance, file=upload(PNG + b'\x00' * 100))

        assert response.status_code == 400 and 'demasiado grande' in response.data['file'][0]
        remittance.refresh_from_db()
        assert not remittance.payment_proof

    def test_a_file_exactly_at_the_limit_is_accepted(self, customer, settings):
        settings.PAYMENT_PROOF_MAX_BYTES = len(PNG)

        assert send(customer, new_remittance(customer), file=upload(PNG)).status_code == 200

    def test_sending_again_replaces_the_file_and_removes_the_old_one(self, customer, isolated_media, django_capture_on_commit_callbacks):
        remittance = new_remittance(customer)
        send(customer, remittance, file=upload(PNG))
        remittance.refresh_from_db()
        first = isolated_media / remittance.payment_proof.name

        with django_capture_on_commit_callbacks(execute=True):
            send(customer, remittance, file=upload(JPG, 'otra.jpg'))

        remittance.refresh_from_db()
        assert not first.exists()
        assert (isolated_media / remittance.payment_proof.name).read_bytes() == JPG
        assert len(list((isolated_media / 'payment_proofs' / remittance.tracking_id).iterdir())) == 1

    def test_a_reference_only_update_keeps_the_existing_file(self, customer, isolated_media):
        remittance = new_remittance(customer)
        send(customer, remittance, file=upload(PNG))
        remittance.refresh_from_db()
        kept = remittance.payment_proof.name

        send(customer, remittance, reference='ZEL-9')

        remittance.refresh_from_db()
        assert remittance.payment_proof.name == kept and (isolated_media / kept).exists()


class TestWhoAndWhen:
    def test_anonymous_gets_401(self, customer):
        assert client_for().post(proof_url(new_remittance(customer)), {'reference': 'x'}, format='multipart').status_code == 401

    def test_someone_elses_remittance_is_a_404_even_for_an_administrator(self, customer, admin):
        remittance = new_remittance(customer)
        other = make_user('otro@example.com')

        assert send(other, remittance, reference='x').status_code == 404
        assert admin.post(proof_url(remittance), {'reference': 'x'}, format='multipart').status_code == 404

    def test_gateway_payments_do_not_take_a_proof(self, customer):
        remittance = new_remittance(customer, method='STRIPE')

        response = send(customer, remittance, reference='x')

        assert response.status_code == 400 and 'en línea' in response.data['detail']

    @pytest.mark.parametrize('status', ['PAID', 'COMPLETED', 'CANCELLED'])
    def test_only_a_remittance_still_waiting_for_payment_takes_a_proof(self, customer, status):
        remittance = new_remittance(customer)
        Remittance.objects.filter(pk=remittance.pk).update(status=status)

        response = send(customer, remittance, reference='x')

        assert response.status_code == 400 and 'ya no está esperando' in response.data['detail']

    def test_the_tracking_id_works_in_lowercase(self, customer):
        remittance = new_remittance(customer)

        response = client_for(customer).post(
            proof_url(remittance).replace(remittance.tracking_id, remittance.tracking_id.lower()),
            {'reference': 'x'}, format='multipart')

        assert response.status_code == 200


class TestWhatTheOwnerSees:
    def test_the_detail_shows_the_reference_whether_a_file_was_sent_and_a_safe_timeline(self, customer):
        remittance = new_remittance(customer)
        send(customer, remittance, reference='ZEL-1', file=upload(PNG))

        data = client_for(customer).get(f'/api/remittances/{remittance.tracking_id}/').data

        assert (data['payment_reference'], data['has_proof_file']) == ('ZEL-1', True)
        assert data['status_log'][0]['to_status'] == 'PENDING_PAYMENT' and data['status_log'][0]['event'] is True
        assert all(set(entry) == {'from_status', 'to_status', 'to_status_display', 'changed_at', 'event'}
                   for entry in data['status_log'])  # no notes, no admin emails
        assert data['status_log'][-1]['event'] is False  # the proof note is not a state change


class TestAdminDownload:
    def test_the_administrator_gets_the_exact_file_with_safe_headers(self, customer, admin):
        remittance = new_remittance(customer)
        send(customer, remittance, file=upload(PNG))

        response = admin.get(admin_proof_url(remittance))

        assert response.status_code == 200
        assert b''.join(response.streaming_content) == PNG
        assert response['Content-Type'] == 'image/png'
        assert response['Content-Disposition'] == f'inline; filename="comprobante-{remittance.tracking_id}.png"'
        assert response['X-Content-Type-Options'] == 'nosniff'
        assert response['Cache-Control'] == 'private, no-store'

    @pytest.mark.parametrize('content, name, mime', [(JPG, 'a.jpg', 'image/jpeg'), (PDF, 'a.pdf', 'application/pdf')])
    def test_the_content_type_follows_the_validated_extension(self, customer, admin, content, name, mime):
        remittance = new_remittance(customer)
        send(customer, remittance, file=upload(content, name))

        assert admin.get(admin_proof_url(remittance))['Content-Type'] == mime

    def test_a_customer_cannot_download_it_not_even_their_own(self, customer):
        remittance = new_remittance(customer)
        send(customer, remittance, file=upload(PNG))

        assert client_for(customer).get(admin_proof_url(remittance)).status_code == 403

    def test_anonymous_gets_401(self, customer):
        remittance = new_remittance(customer)
        send(customer, remittance, file=upload(PNG))

        assert client_for().get(admin_proof_url(remittance)).status_code == 401

    def test_no_file_is_a_404(self, customer, admin):
        remittance = new_remittance(customer)
        send(customer, remittance, reference='ZEL-1')  # reference only

        assert admin.get(admin_proof_url(remittance)).status_code == 404

    def test_the_admin_detail_says_whether_there_is_a_file(self, customer, admin):
        remittance = new_remittance(customer)
        send(customer, remittance, reference='ZEL-1', file=upload(PNG))

        data = admin.get(f'/api/admin/remittances/{remittance.tracking_id}/').data

        assert (data['payment_reference'], data['has_proof_file']) == ('ZEL-1', True)
        assert 'comprobante' in data['status_log'][-1]['note']

    def test_the_inbox_flags_remittances_that_have_a_proof(self, customer, admin):
        with_proof, without = new_remittance(customer), new_remittance(customer)
        send(customer, with_proof, reference='ZEL-1')

        rows = {r['tracking_id']: r['has_proof'] for r in admin.get('/api/admin/remittances/').data['results']}

        assert rows == {with_proof.tracking_id: True, without.tracking_id: False}


class TestNoPublicUrl:
    def test_the_media_folder_is_not_served(self, customer, isolated_media):
        remittance = new_remittance(customer)
        send(customer, remittance, file=upload(PNG))
        remittance.refresh_from_db()

        for path in (f'/media/{remittance.payment_proof.name}', f'/{remittance.payment_proof.name}', '/media/'):
            assert client_for().get(path).status_code == 404
