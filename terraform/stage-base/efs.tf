resource "aws_efs_file_system" "influxdb" {
  creation_token   = "wfm-stage-influxdb"
  encrypted        = true
  performance_mode = "generalPurpose"
  throughput_mode  = "bursting"

  tags = {
    Name = "wfm-stage-influxdb-efs"
  }
}

# Backup automat dezactivat explicit (cost); in productie l-am activa
resource "aws_efs_backup_policy" "influxdb" {
  file_system_id = aws_efs_file_system.influxdb.id

  backup_policy {
    status = "DISABLED"
  }
}

# Cate o "priza" EFS in fiecare subretea privata (ambele AZ-uri)
resource "aws_efs_mount_target" "influxdb" {
  count = length(module.network.private_subnet_ids)

  file_system_id  = aws_efs_file_system.influxdb.id
  subnet_id       = module.network.private_subnet_ids[count.index]
  security_groups = [aws_security_group.efs.id]
}

# Intrarea pentru InfluxDB: forteaza uid/gid 1000 si subfolderul /influxdb
resource "aws_efs_access_point" "influxdb" {
  file_system_id = aws_efs_file_system.influxdb.id

  posix_user {
    uid = 1000
    gid = 1000
  }

  root_directory {
    path = "/influxdb"

    creation_info {
      owner_uid   = 1000
      owner_gid   = 1000
      permissions = "0750"
    }
  }

  tags = {
    Name = "wfm-stage-influxdb-ap"
  }
}
