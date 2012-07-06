from django.http import Http404, HttpResponse
from django.views.generic import ListView, DetailView
from django.shortcuts import get_object_or_404, render

from .models import Project, Category
from .forms import BackerForm

class ProjectListView(ListView):

    context_object_name = "project_list"
    queryset = Project.objects.all().select_related()
    model = Project

    def get_context_data(self, **kwargs):
        context = super(ProjectListView, self).get_context_data(**kwargs)
        context['categoriy_list'] = Category.objects.all()
        return context


class ProjectCategoryListView(ListView):

    context_object_name = "project_list"
    model = Project

    def get_context_data(self, **kwargs):
        context = super(ProjectCategoryListView, self).get_context_data(**kwargs)
        context['categoriy_list'] = Category.objects.all()
        return context

    def get_queryset(self):
        category = get_object_or_404(Category, slug=self.kwargs['slug'])
        return Project.objects.filter(categories=category)

class ProjectDetailView(DetailView):

    context_object_name = "project"
    model = Project

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        response = self.prepare()
        if response:
            return response

        response = self.render_to_response(self.get_context_data(object=self.object))
        return self.finalize(response)

    def post(self, request, *args, **kwargs):
        return self.get(request, *args, **kwargs)

    def prepare(self):
        """
        Prepare / pre-process content types. If this method returns anything,
        it is treated as a ``HttpResponse`` and handed back to the visitor.
        """

        http404 = None     # store eventual Http404 exceptions for re-raising,
                           # if no content type wants to handle the current self.request
        successful = False # did any content type successfully end processing?

        contents = tuple(self.object._feincms_content_types_with_process)
        for content in self.object.content.all_of_type(contents):
            try:
                r = content.process(self.request, view=self)
                if r in (True, False):
                    successful = r
                elif r:
                    return r
            except Http404, e:
                http404 = e

        if not successful:
            if http404:
                # re-raise stored Http404 exception
                raise http404

    def finalize(self, response):
        """
        Runs finalize() on content types having such a method, adds headers and
        returns the final response.
        """

        if not isinstance(response, HttpResponse):
            # For example in the case of inheritance 2.0
            return response

        contents = tuple(self.object._feincms_content_types_with_finalize)
        for content in self.object.content.all_of_type(contents):
            r = content.finalize(self.request, response)
            if r:
                return r

        return response


def project_back_form(request, slug):
    project = get_object_or_404(Project, slug=slug)

    form = BackerForm()

    return render(request, 'zipfelchappe/project_back_form.html', {
        'project': project,
        'form': form
    })