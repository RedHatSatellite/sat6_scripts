Name:           sat6_scripts
Version:        1.2.4
Release:        1%{?dist}
Summary:        Scripts to automate Satellite 6 tasks

License:        GPL
URL:            https://github.com/RedHatSatellite/sat6_scripts
Source0:        sat6_scripts-1.2.4.tar.gz

Requires:       python >= 2.7, PyYAML

%description
Various scripts to substantially automate management tasks of Satellite 6, including:
- content export/import in disconnected environments,
- content publish/promote activities


%prep
%autosetup


%build


%install
rm -rf %{buildroot}
mkdir -p %{buildroot}/usr/local/{bin,etc/sat6_scripts,share/man/man8}
mkdir -p %{buildroot}/usr/share/{doc/sat6_scripts,sat6_scripts/config}
install -m 0644 README.md %{buildroot}/usr/share/doc/sat6_scripts/README.md
install -m 0644 CHANGELOG.md %{buildroot}/usr/share/doc/sat6_scripts/CHANGELOG.md
install -m 0644 LICENSE %{buildroot}/usr/share/doc/sat6_scripts/LICENSE
install -m 0644 docs/sat62_install.txt %{buildroot}/usr/share/doc/sat6_scripts/sat62_install.txt
install -m 0644 docs/sat62disc_install.txt %{buildroot}/usr/share/doc/sat6_scripts/sat62disc_install.txt
install -m 0644 docs/sat62_hardening.txt %{buildroot}/usr/share/doc/sat6_scripts/sat62_hardening.txt
install -m 0644 config/config.yml.example %{buildroot}/usr/share/sat6_scripts/config/config.yml
install -m 0644 config/exports.yml.example %{buildroot}/usr/share/sat6_scripts/config/exports.yml
install -m 0755 bin/check_sync %{buildroot}/usr/local/bin/check_sync
install -m 0755 bin/sat_export %{buildroot}/usr/local/bin/sat_export
install -m 0755 bin/sat_import %{buildroot}/usr/local/bin/sat_import
install -m 0755 bin/auto_content %{buildroot}/usr/local/bin/auto_content
install -m 0755 bin/clean_content_views %{buildroot}/usr/local/bin/clean_content_views
install -m 0755 bin/publish_content_views %{buildroot}/usr/local/bin/publish_content_views
install -m 0755 bin/promote_content_views %{buildroot}/usr/local/bin/promote_content_views
install -m 0755 bin/download_manifest %{buildroot}/usr/local/bin/download_manifest
install -m 0755 bin/push_puppetforge %{buildroot}/usr/local/bin/push_puppetforge
install -m 0644 helpers.py %{buildroot}/usr/share/sat6_scripts/helpers.py
install -m 0644 auto_content.py %{buildroot}/usr/share/sat6_scripts/auto_content.py
install -m 0644 check_sync.py %{buildroot}/usr/share/sat6_scripts/check_sync.py
install -m 0644 sat_export.py %{buildroot}/usr/share/sat6_scripts/sat_export.py
install -m 0644 sat_import.py %{buildroot}/usr/share/sat6_scripts/sat_import.py
install -m 0644 publish_content_views.py %{buildroot}/usr/share/sat6_scripts/publish_content_views.py
install -m 0644 promote_content_views.py %{buildroot}/usr/share/sat6_scripts/promote_content_views.py
install -m 0644 clean_content_views.py %{buildroot}/usr/share/sat6_scripts/clean_content_views.py
install -m 0644 download_manifest.py %{buildroot}/usr/share/sat6_scripts/download_manifest.py
install -m 0644 push_puppetforge.py %{buildroot}/usr/share/sat6_scripts/push_puppetforge.py

gzip -9c man/check_sync.8 > %{buildroot}/usr/local/share/man/man8/check_sync.8.gz
gzip -9c man/clean_content_views.8 > %{buildroot}/usr/local/share/man/man8/clean_content_views.8.gz
gzip -9c man/download_manifest.8 > %{buildroot}/usr/local/share/man/man8/download_manifest.8.gz
gzip -9c man/publish_content_views.8 > %{buildroot}/usr/local/share/man/man8/publish_content_views.8.gz
gzip -9c man/promote_content_views.8 > %{buildroot}/usr/local/share/man/man8/promote_content_views.8.gz
gzip -9c man/push_puppetforge.8 > %{buildroot}/usr/local/share/man/man8/push_puppetforge.8.gz
gzip -9c man/sat6_scripts.8 > %{buildroot}/usr/local/share/man/man8/sat6_scripts.8.gz
gzip -9c man/sat_export.8 > %{buildroot}/usr/local/share/man/man8/sat_export.8.gz
gzip -9c man/sat_import.8 > %{buildroot}/usr/local/share/man/man8/sat_import.8.gz


%files
%doc /usr/share/doc/sat6_scripts/README.md
%doc /usr/share/doc/sat6_scripts/CHANGELOG.md
%doc /usr/share/doc/sat6_scripts/sat62_install.txt
%doc /usr/share/doc/sat6_scripts/sat62disc_install.txt
%doc /usr/share/doc/sat6_scripts/sat62_hardening.txt
%license /usr/share/doc/sat6_scripts/LICENSE
%config(noreplace) /usr/share/sat6_scripts/config/config.yml
%config(noreplace) /usr/share/sat6_scripts/config/exports.yml

/usr/local/share/man/man8/check_sync.8.gz
/usr/local/share/man/man8/clean_content_views.8.gz
/usr/local/share/man/man8/download_manifest.8.gz
/usr/local/share/man/man8/publish_content_views.8.gz
/usr/local/share/man/man8/promote_content_views.8.gz
/usr/local/share/man/man8/push_puppetforge.8.gz
/usr/local/share/man/man8/sat6_scripts.8.gz
/usr/local/share/man/man8/sat_export.8.gz
/usr/local/share/man/man8/sat_import.8.gz

/usr/share/sat6_scripts/helpers.py
/usr/share/sat6_scripts/auto_content.py
/usr/share/sat6_scripts/check_sync.py
/usr/share/sat6_scripts/sat_export.py
/usr/share/sat6_scripts/sat_import.py
/usr/share/sat6_scripts/publish_content_views.py
/usr/share/sat6_scripts/promote_content_views.py
/usr/share/sat6_scripts/clean_content_views.py
/usr/share/sat6_scripts/download_manifest.py
/usr/share/sat6_scripts/push_puppetforge.py

/usr/local/bin/auto_content
/usr/local/bin/check_sync
/usr/local/bin/sat_export
/usr/local/bin/sat_import
/usr/local/bin/clean_content_views
/usr/local/bin/publish_content_views
/usr/local/bin/promote_content_views
/usr/local/bin/download_manifest
/usr/local/bin/push_puppetforge

%exclude /usr/share/sat6_scripts/*.pyc
%exclude /usr/share/sat6_scripts/*.pyo

%post
# Only run on initial install
if [ $1 -eq 1 ]; then
  mkdir -p /usr/local/etc/sat6_scripts > /dev/null
  ln -s /usr/share/sat6_scripts/config/config.yml /usr/local/etc/sat6_scripts/config.yml
  ln -s /usr/share/sat6_scripts/config/exports.yml /usr/local/etc/sat6_scripts/exports.yml
fi
# Update man DB
mandb -q

%postun
# Only run on a complete uninstall
if [ $1 -eq 0 ]; then
  unlink /usr/local/etc/sat6_scripts/config.yml
  unlink /usr/local/etc/sat6_scripts/exports.yml
fi
# Update man DB
mandb -q


%changelog
* Sun Nov 25 2018 Geoff Gatward <ggatward@redhat.com> 1.2.4
- Refer https://github.com/RedHatSatellite/sat6_scripts/blob/1.2.4/CHANGELOG.md

* Mon Mar 12 2018 Geoff Gatward <ggatward@redhat.com> 1.2.3
- Refer https://github.com/RedHatSatellite/sat6_scripts/blob/1.2.3/CHANGELOG.md

* Sun Feb 25 2018 Geoff Gatward <ggatward@redhat.com> 1.2.2
- Refer https://github.com/RedHatSatellite/sat6_scripts/blob/1.2.2/CHANGELOG.md

* Mon Dec 11 2017 Geoff Gatward <ggatward@redhat.com> 1.2.1
- Refer https://github.com/RedHatSatellite/sat6_scripts/blob/1.2.1/CHANGELOG.md

* Sun Dec 10 2017 Geoff Gatward <ggatward@redhat.com> 1.2.0
- Refer https://github.com/RedHatSatellite/sat6_scripts/blob/1.2.0/CHANGELOG.md

* Wed Oct 25 2017 Geoff Gatward <ggatward@redhat.com> 1.1.1
- Refer https://github.com/ggatward/sat6_scripts/blob/1.1.1/CHANGELOG.md

* Thu Oct 19 2017 Geoff Gatward <ggatward@redhat.com> 1.1.0
- Refer https://github.com/ggatward/sat6_scripts/blob/1.1.0/CHANGELOG.md

* Mon Mar 06 2017 Geoff Gatward <ggatward@redhat.com> 1.0
- Production release

* Mon Feb 27 2017 Geoff Gatward <ggatward@redhat.com> 0.6
- Beta 6

* Wed Jan 4 2017 Geoff Gatward <ggatward@redhat.com> 0.5
- Beta 5

* Tue Jan 3 2017 Geoff Gatward <ggatward@redhat.com> 0.4
- Beta 4

* Tue Jan 3 2017 Geoff Gatward <ggatward@redhat.com> 0.3
- Beta 3

* Tue Dec 20 2016 Geoff Gatward <ggatward@redhat.com> 0.2
- Beta 2

* Tue Dec 20 2016 Geoff Gatward <ggatward@redhat.com> 0.1
- Initial RPM release
