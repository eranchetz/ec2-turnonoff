data "archive_file" "ec2-turnonoff-py" {
    type        = "zip"
    source_file = "${path.module}/lambda_function.py"
    output_path = "${path.module}/ec2-turnonoff.zip"
}

resource "aws_iam_role" "lambda_ec2_turnonoff" {
    name = "lambda_ec2_turnonoff"

    assume_role_policy = <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Action": "sts:AssumeRole",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Effect": "Allow",
      "Sid": ""
    }
  ]
}
EOF
}


resource "aws_iam_role_policy" "lambda_ec2_turnonoff_policy" {
    name = "lambda_ec2_turnonoff_policy"
    role = "${aws_iam_role.lambda_ec2_turnonoff.id}"

    policy = <<EOF
{  
   "Version":"2012-10-17",
   "Statement":[  
      {  
         "Effect":"Allow",
         "Action":[  
            "logs:CreateLogGroup",
            "logs:CreateLogStream",
            "logs:PutLogEvents"
         ],
         "Resource":"arn:aws:logs:*:*:*"
      },
      {  
         "Effect":"Allow",
         "Action":[  
            "ec2:DescribeRegions",
            "ec2:DescribeInstances"
         ],
         "Resource":"*"
      },
      {  
         "Sid":"VisualEditor0",
         "Effect":"Allow",
         "Action":[  
            "ec2:StartInstances"
         ],
         "Resource":"*",
         "Condition":{  
            "StringLike":{  
               "ec2:ResourceTag/TurnOn":"*"
            }
         }
      },
      {  
         "Sid":"VisualEditor1",
         "Effect":"Allow",
         "Action":[  
            "ec2:StopInstances"
         ],
         "Resource":"*",
         "Condition":{  
            "StringLike":{  
               "ec2:ResourceTag/TurnOff":"*"
            }
         }
      }
   ]
}
EOF
}

variable "workweek" {
  default = "Monday"
}


resource "aws_lambda_function" "lambda_ec2_turnonoff" {
    filename = "${path.module}/ec2-turnonoff.zip"
    function_name = "EC2_TurnOnOff"
    role = "${aws_iam_role.lambda_ec2_turnonoff.arn}"
    handler = "lambda_function.lambda_handler"
    source_code_hash = "${data.archive_file.ec2-turnonoff-py.output_base64sha256}"
    runtime = "python3.7"
    timeout = 900
	  environment {
    	  	variables = {
	  		workweek_tag  = "${var.workweek}"
	  	}
	  }
}

resource "aws_cloudwatch_event_rule" "lambda_ec2_turnonoff" {
    name = "lambda_ec2_turnonoff"
    description = "Invoke lambda every half an hour"
    schedule_expression = "cron(0/30 * * * ? *)"
}

resource "aws_cloudwatch_event_target" "lambda_ec2_turnonoff" {
    rule = "${aws_cloudwatch_event_rule.lambda_ec2_turnonoff.name}"
    target_id = "ec2-turnonoff"
    arn = "${aws_lambda_function.lambda_ec2_turnonoff.arn}"
}

resource "aws_lambda_permission" "lambda_ec2_turnonoff" {
    statement_id = "AllowExecutionFromCloudWatch"
    action = "lambda:InvokeFunction"
    function_name = "${aws_lambda_function.lambda_ec2_turnonoff.function_name}"
    principal = "events.amazonaws.com"
    source_arn = "${aws_cloudwatch_event_rule.lambda_ec2_turnonoff.arn}"
}
