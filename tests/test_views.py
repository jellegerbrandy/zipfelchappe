from __future__ import absolute_import, unicode_literals
from django.core import mail
from django.test import TestCase
from django.test.client import Client
from django.utils import timezone

from feincms.module.page.models import Page
from feincms.content.application.models import ApplicationContent

from bs4 import BeautifulSoup


from tests.factories import ProjectFactory, RewardFactory, PledgeFactory, UserFactory
from zipfelchappe.models import Backer, Pledge
from zipfelchappe import app_settings


class PledgeWorkflowTest(TestCase):
    login_url = '/accounts/login/'

    def setUp(self):
        # feincms page containing zipfelchappe app content
        self.page = Page.objects.create(title='Projects', slug='projects')
        ct = self.page.content_type_for(ApplicationContent)
        ct.objects.create(parent=self.page, urlconf_path=app_settings.ROOT_URLS)

        # Fixture Data for following tests
        self.project1 = ProjectFactory.create()
        self.project2 = ProjectFactory.create()
        self.user = UserFactory.create()
        self.reward = RewardFactory.create(
            project=self.project1,
            minimum=20.00,
            quantity=1
        )

        # Fresh Client for every test
        self.client = Client()

    def tearDown(self):
        mail.outbox = []

    def assertRedirect(self, response, expected_url):
        """ Just check immediate redirect, don't follow target url """
        full_url = ('Location', 'http://testserver' + expected_url)
        self.assertIn('location', response._headers)
        self.assertEqual(response._headers['location'], full_url)
        self.assertEqual(response.status_code, 302)

    def test_project_list(self):
        """ Basic check if projects are visible in list """
        r = self.client.get('/projects/')
        self.assertEqual(200, r.status_code)
        soup = BeautifulSoup(str(r))

        # There should be two projects total
        project_links = soup.find_all('a', class_='project')
        self.assertEqual(2, len(project_links))

        # Check first project has correct url
        project1_url = self.project1.get_absolute_url()
        self.assertEqual(project_links[0]['href'], project1_url)

    def test_project_detail(self):
        """ Check if project detail page infos are correct """
        r = self.client.get(self.project1.get_absolute_url())
        self.assertEqual(200, r.status_code)
        soup = BeautifulSoup(str(r))

        # Project should not have any pledges yet
        achieved = soup.find(class_='progress').find(class_='info')
        self.assertEqual('0 CHF (0%)', achieved.text.strip())

        # Project should be backable
        back_button = soup.find(id='back_button')
        self.assertIsNotNone(back_button)

    def test_back_project(self):
        """ Does the back form show up the right way? """
        r = self.client.get('/projects/back/%s/' % self.project1.slug)

        # There should be a reward
        self.assertContains(r, 'testreward')

    def test_back_expired_project(self):
        """ Trying to back an expired project should return a redirect. """
        self.project1.end = timezone.now()
        self.project1.save()
        r = self.client.get('/projects/back/%s/' % self.project1.slug)
        self.assertRedirect(r, '/projects/project/%s/' % self.project1.slug)

    def test_amount_fits_reward(self):
        """ Validation should prevent to small amounts for selected rewards """
        r = self.client.post('/projects/back/%s/' % self.project1.slug, {
            'project': self.project1.id,
            'amount': '10',
            'reward': self.reward.id,
            'provider': 'paypal'
        })

        self.assertContains(r, 'Amount is to low for a reward!')

    def test_unavailable_rewards(self):
        # Validation should prevent to choose awards that are given away
        url = '/projects/back/%s/' % self.project1.slug

        # Give away the limited reward
        PledgeFactory.create(
            project=self.project1,
            amount=25.00,
            reward=self.reward
        )

        # Try to create pledge with unavailable reward
        response = self.client.post(url, {
            'project': self.project1.id,
            'amount': '20',
            'reward': self.reward.id
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Sorry, this reward is not available anymore.')

    def test_available_rewards(self):
        url = '/projects/back/%s/' % self.project1.slug
        self.reward.quantity = 0  # unlimited
        self.reward.save()
        # Try to create pledge with unavailable reward
        response = self.client.post(url, {
            'project': self.project1.id,
            'amount': '20',
            'provider': 'paypal',
            'reward': self.reward.id
        })
        self.assertEqual(response.status_code, 302)

    def test_pledge_with_login(self):
        # Submit pledge data
        r = self.client.post('/projects/back/%s/' % self.project1.slug, {
            'project': self.project1.id,
            'amount': '20',
            'reward': self.reward.id,
            'provider': 'paypal'
        })

        # Should redirect to authenticate view
        self.assertRedirect(r, '/projects/backer/authenticate/')
        r = self.client.get(r.url)

        # Should redirect to login/register
        self.assertRedirect(
            r,
            '?'.join([self.login_url, 'next=/projects/backer/authenticate/'])
        )

        # A pledge should now be associated with the session
        self.assertIn('pledge_id', self.client.session)

        self.client.login(username=self.user, password='test')
        # Finally, we should get redirect to the payment viewew
        r = self.client.get('/projects/backer/authenticate/')
        self.assertRedirect(r, '/paypal/')
        self.client.session.delete('pledge_id')

    def test_pledge_already_logged_in(self):
        self.client.login(username=self.user.username, password='test')

        # Submit pledge data
        r = self.client.post('/projects/back/%s/' % self.project1.slug, {
            'project': self.project1.id,
            'amount': '20',
            'reward': self.reward.id,
            'provider': 'paypal'
        })
        # Should redirect to to authentication page
        self.assertRedirect(r, '/projects/backer/authenticate/')

        # A pledge should now be associated with the session
        self.assertIn('pledge_id', self.client.session)

        # Connect user with pledge
        r = self.client.get(r.url)

        # A backer model should have been created for this user
        try:
            Backer.objects.get(user=self.user)
        except Backer.DoesNotExist:
            self.fail('Backer model for authenticated user not created')

        # Next redirect should go to payment directly
        self.assertRedirect(r, '/paypal/')
        self.assertIn('pledge_id', self.client.session)


    def test_thankyou_page(self):
        self.client.login(username=self.user.username, password='test')
        # Submit pledge data
        response = self.client.post('/projects/back/%s/' % self.project1.slug, {
            'project': self.project1.id,
            'amount': '20',
            'reward': self.reward.id,
            'provider': 'paypal'
        })
        self.assertRedirect(response, '/projects/backer/authenticate/')
        self.assertIn('pledge_id', self.client.session)
        response = self.client.get('/projects/backer/authenticate/')

        pledge = Pledge.objects.get(backer__user=self.user, project=self.project1)

        self.assertEquals(self.client.session['pledge_id'], pledge.id)
        response = self.client.get('/projects/pledge/thankyou/')
        self.assertRedirect(response, '/projects/project/%s/backed/' % self.project1.slug)
        self.assertNotIn('pledge_id', self.client.session)
        self.assertIn('completed_pledge_id', self.client.session)
        # test mail has been sent.
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, 'Thank you for supporting %s' % pledge.project)

        response = self.client.get('/projects/project/%s/backed/' % self.project1.slug)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('pledge_id', self.client.session)
        self.assertNotIn('completed_pledge_id', self.client.session)
        self.assertContains(response, self.project1.title)